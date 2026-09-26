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
from typing import Any, Callable, Mapping, Optional, Sequence

from openbb_backend.symbol_names import display_name, resolve_symbol_names
from stock_checker.trade_postmortem import DEFAULT_LIMIT as POSTMORTEM_LIMIT
from stock_checker.trade_postmortem import closed_rounds


def load_json_checked(path: Path, default: Any) -> tuple[Any, dict[str, Any]]:
    """Parse one JSON file. Report missing, ok, malformed, or unreadable.

    A bad file returns ``default``. Callers must not treat that as an empty book.
    """
    if not path.exists():
        return default, {"state": "missing", "bad": 0}
    try:
        text = path.read_text()
    except OSError:
        return default, {"state": "unreadable", "bad": 1}
    try:
        return json.loads(text), {"state": "ok", "bad": 0}
    except json.JSONDecodeError:
        return default, {"state": "malformed", "bad": 1}


def load_jsonl_checked(path: Path) -> tuple[list[dict], dict[str, Any]]:
    """Parse JSONL. Keep good rows. Count bad lines. Do not drop the file.

    One bad line used to wipe the ledger. ``thin`` means some rows survived.
    ``malformed`` means the file exists but every non-empty line failed.
    """
    if not path.exists():
        return [], {"state": "missing", "bad": 0, "good": 0}
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return [], {"state": "unreadable", "bad": 1, "good": 0}
    rows: list[dict] = []
    bad = 0
    for line in lines:
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            bad += 1
            continue
        if isinstance(obj, dict):
            rows.append(obj)
        else:
            bad += 1
    if bad == 0:
        state = "ok"
    elif rows:
        state = "thin"
    else:
        state = "malformed"
    return rows, {"state": state, "bad": bad, "good": len(rows)}


def _load_json(path: Path, default: Any) -> Any:
    doc, _meta = load_json_checked(path, default)
    return doc


def _load_jsonl(path: Path) -> list[dict]:
    rows, _meta = load_jsonl_checked(path)
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


def build_mark_coverage(
    rows: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """Holding price-coverage honesty (xang1234 Cot stale-coverage reject; display only).

    Scan age is ``build_scan_freshness``. This counts lots with a live mark
    versus cost fallback. ok = all marked. thin = some cost fallback.
    none = no marks. An empty book stays silent. Not an entry gate.
    Cost fallback still fills equity when marks are missing.
    """
    empty = {
        "ready": False,
        "tone": "flat",
        "severity": "",
        "marked": 0,
        "open": 0,
        "pct": None,
        "bit": "",
        "line": "",
    }
    lots = [r for r in (rows or []) if isinstance(r, dict)]
    n = len(lots)
    if n <= 0:
        return empty
    marked = sum(1 for r in lots if r.get("marked"))
    if marked <= 0:
        bit = f"price coverage none · 0/{n}"
        return {
            "ready": True,
            "tone": "warn",
            "severity": "none",
            "marked": 0,
            "open": n,
            "pct": 0.0,
            "bit": bit,
            "line": bit,
        }
    if marked >= n:
        bit = f"price coverage ok · {n}/{n}"
        return {
            "ready": True,
            "tone": "ok",
            "severity": "ok",
            "marked": marked,
            "open": n,
            "pct": 100.0,
            "bit": bit,
            "line": bit,
        }
    bit = f"price coverage thin · {marked}/{n}"
    return {
        "ready": True,
        "tone": "warn",
        "severity": "thin",
        "marked": marked,
        "open": n,
        "pct": round(100.0 * marked / n, 1),
        "bit": bit,
        "line": bit,
    }


def build_ledger_health(data_dir: Path | str) -> dict[str, Any]:
    """Report portfolio.json / trades.jsonl parse health (display only).

    tradermonty #411: name a malformed shard. Do not show an empty book as truth.
    A thin trades file keeps good rows and says the ledger is partial (#416).
    Missing both files stays silent. Not an entry gate.
    """
    empty = {
        "ready": False,
        "tone": "flat",
        "severity": "",
        "bit": "",
        "line": "",
        "portfolio_state": "missing",
        "trades_state": "missing",
        "bad_lines": 0,
        "good_lines": 0,
    }
    root = Path(data_dir)
    port_doc, port = load_json_checked(root / "portfolio.json", {})
    if port["state"] == "ok" and not isinstance(port_doc, dict):
        port = {"state": "malformed", "bad": 1}
    _rows, trades = load_jsonl_checked(root / "trades.jsonl")
    port_state = str(port.get("state") or "missing")
    trades_state = str(trades.get("state") or "missing")
    if port_state == "missing" and trades_state == "missing":
        return empty

    problems: list[str] = []
    severity = "ok"
    if port_state == "malformed":
        severity = "bad"
        problems.append("portfolio malformed")
    elif port_state == "unreadable":
        severity = "bad"
        problems.append("portfolio unreadable")
    elif port_state == "missing":
        severity = "thin"
        problems.append("no portfolio")

    bad_lines = int(trades.get("bad") or 0)
    if trades_state == "thin":
        if severity != "bad":
            severity = "thin"
        label = "1 bad line" if bad_lines == 1 else f"{bad_lines} bad lines"
        problems.append(label)
    elif trades_state == "malformed":
        severity = "bad"
        problems.append("trades malformed")
    elif trades_state == "unreadable":
        severity = "bad"
        problems.append("trades unreadable")

    if severity == "ok":
        bit = "ledger ok"
    else:
        bit = f"ledger {severity} · " + " · ".join(problems)
    return {
        "ready": True,
        "tone": "ok" if severity == "ok" else "warn",
        "severity": severity,
        "bit": bit,
        "line": bit,
        "portfolio_state": port_state,
        "trades_state": trades_state,
        "bad_lines": bad_lines,
        "good_lines": int(trades.get("good") or 0),
    }


def build_soft_allow_glance(
    events: list[dict[str, Any]] | None,
    *,
    now: datetime | None = None,
    fresh_hours: float | None = None,
    aging_hours: float | None = None,
) -> dict[str, Any]:
    """Compact fail-open soft-allow memory (tradermonty; display only).

    Shows only when the ring buffer has rows — links friends to Ops detail.
    Soft-allows use a fresh / aging / expired triad (xang1234 + RyanJHamby
    scan-age pattern): aging after ``aging_hours``, expired after
    ``fresh_hours``. Speak fresh + aging + expired counts (+ gate tallies)
    so friends see live fail-opens beside rows that cool off.

    Cool-off severity (portfolio AI quiet vs high + xang1234): ``hot`` when
    any fresh row remains (tone warn); ``aging`` when only aging cools
    (tone flat); ``cool`` when the ring is all expired (tone flat). Expired
    diagnostics stay visible — they are not a hot fail-open.

    Lead gate (portfolio AI concentration + xang1234): when the
    severity-driving band has a clear dominant gate (≥2 and strictly
    ahead of #2), speak ``rs leads · fresh|aging|expired · ×N · M% ·
    ahead … · vs gate ×K · P% · share Δ wide|thin · ±Npp · share vs Δ
    clash|align`` after severity — band identity matches Ops
    ``leads · band`` (concentration is within the severity band, not the
    whole ring); tally alone does not name the concentration; ahead
    margin ≠ who is runner-up; absolute ×K ≠ runner band ownership; two
    % ≠ the ownership spread (mid silent); count-ahead lean ≠
    ownership-Δ lean (clash when share mid; align when same lean;
    different lean silent).     Ops lead inventory reuses the same share /
    ahead margin / Δ / vs-Δ fields so ``Lead · gate ×N · band · M% ·
    ahead … · +K`` shows ownership and how far ahead (counts ≠ share ≠
    margin) without parsing the glance line. Ops runner inventory speaks
    ``Runner · gate ×K · band · P%`` on its own line when ahead already
    spoke; when margin spoke it also shows ``behind … · −K`` (same K,
    speak-both-sides; not a lead÷runner ratio; not buried in Lead).
    """
    from stock_checker.gate_audit import (
        SOFT_ALLOW_AGING_HOURS,
        SOFT_ALLOW_FRESH_HOURS,
        enrich_soft_allows,
        format_aging_soft_allow_tally,
        format_expired_soft_allow_tally,
        format_fresh_soft_allow_tally,
        format_soft_allow_lead_bit,
        soft_allow_lead_margin,
        soft_allow_lead_share,
        soft_allow_lead_sides_share,
        soft_allow_lead_sides_share_delta,
        soft_allow_lead_sides_share_vs_delta,
    )

    ttl = float(SOFT_ALLOW_FRESH_HOURS if fresh_hours is None else fresh_hours)
    aging_ttl = float(
        SOFT_ALLOW_AGING_HOURS if aging_hours is None else aging_hours
    )
    empty = {
        "ready": False,
        "tone": "flat",
        "severity": "",
        "count": 0,
        "fresh_count": 0,
        "aging_count": 0,
        "expired_count": 0,
        "fresh_hours": ttl,
        "aging_hours": aging_ttl,
        "fresh_tally": "",
        "aging_tally": "",
        "expired_tally": "",
        "lead_gate": "",
        "lead_count": 0,
        "lead_share_pct": None,
        "lead_margin": None,
        "lead_margin_severity": "",
        "lead_runner_gate": "",
        "lead_runner_count": 0,
        "lead_runner_share_pct": None,
        "lead_share_delta_pp": None,
        "lead_share_delta_severity": "",
        "lead_share_vs_delta": "",
        "lead_share_vs_delta_ahead": "",
        "lead_share_vs_delta_share": "",
        "lead_band": "",
        "lead_bit": "",
        "line": "",
        "last_gate": "",
        "last_reason": "",
    }
    rows = enrich_soft_allows(
        events, now=now, fresh_hours=ttl, aging_hours=aging_ttl
    )
    if not rows:
        return empty
    last = rows[0]
    gate = str(last.get("gate") or "?").strip() or "?"
    reason = str(last.get("reason") or "").strip()
    reason_short = reason if len(reason) <= 72 else (reason[:71] + "…")
    n = len(rows)
    expired_n = sum(1 for r in rows if r.get("freshness") == "expired")
    aging_n = sum(1 for r in rows if r.get("freshness") == "aging")
    fresh_n = sum(1 for r in rows if r.get("freshness") == "fresh")
    # Unknown stamps count with fresh (fail-open — do not hide).
    unknown_n = n - expired_n - aging_n - fresh_n
    fresh_n += unknown_n
    fresh_tally = format_fresh_soft_allow_tally(rows) if fresh_n else ""
    aging_tally = format_aging_soft_allow_tally(rows) if aging_n else ""
    expired_tally = format_expired_soft_allow_tally(rows) if expired_n else ""
    noun = "soft-allow" if n == 1 else "soft-allows"

    def _append_band(
        parts: list[str], label: str, count: int, tally: str
    ) -> None:
        if count <= 0:
            return
        parts.append(f"{count} {label}")
        if tally:
            parts.append(tally)

    if expired_n == 0 and aging_n == 0:
        parts = [f"{n} recent {noun}"]
        if fresh_tally and (fresh_n > 1 or " · " in fresh_tally):
            parts.append(fresh_tally)
        parts.append(f"last [{gate}]")
        line = " · ".join(parts)
    elif fresh_n == 0 and aging_n == 0:
        line = f"{n} expired {noun}"
        if expired_tally:
            line = f"{line} · {expired_tally}"
        line = f"{line} · last [{gate}]"
    else:
        parts = [f"{n} {noun}"]
        _append_band(parts, "fresh", fresh_n, fresh_tally)
        _append_band(parts, "aging", aging_n, aging_tally)
        _append_band(parts, "expired", expired_n, expired_tally)
        parts.append(f"last [{gate}]")
        line = " · ".join(parts)
    if fresh_n > 0:
        severity = "hot"
        tone = "warn"
        lead_band = "fresh"
    elif aging_n > 0:
        severity = "aging"
        tone = "flat"
        lead_band = "aging"
    else:
        severity = "cool"
        tone = "flat"
        lead_band = "expired"
    lead_bit = format_soft_allow_lead_bit(rows, band=lead_band)
    lead = soft_allow_lead_share(rows, band=lead_band)
    margin = soft_allow_lead_margin(rows, band=lead_band)
    sides = soft_allow_lead_sides_share(rows, band=lead_band)
    share_delta = soft_allow_lead_sides_share_delta(rows, band=lead_band)
    share_vs = soft_allow_lead_sides_share_vs_delta(rows, band=lead_band)
    lead_gate = lead[0] if lead else ""
    lead_count = lead[1] if lead else 0
    lead_share_pct = lead[2] if lead else None
    lead_margin = margin[3] if margin else None
    lead_margin_severity = margin[4] if margin else ""
    lead_runner_gate = sides[5] if sides else ""
    lead_runner_count = sides[6] if sides else 0
    lead_runner_share_pct = sides[7] if sides else None
    lead_share_delta_pp = share_delta[8] if share_delta else None
    lead_share_delta_severity = share_delta[9] if share_delta else ""
    lead_share_vs_delta = share_vs[0] if share_vs else ""
    lead_share_vs_delta_ahead = share_vs[1] if share_vs else ""
    lead_share_vs_delta_share = share_vs[2] if share_vs else ""
    if lead_bit:
        line = f"{severity} · {lead_bit} · {line}"
    else:
        line = f"{severity} · {line}"
    if reason_short:
        line = f"{line} {reason_short}"
    return {
        "ready": True,
        "tone": tone,
        "severity": severity,
        "count": n,
        "fresh_count": fresh_n,
        "aging_count": aging_n,
        "expired_count": expired_n,
        "fresh_hours": ttl,
        "aging_hours": aging_ttl,
        "fresh_tally": fresh_tally,
        "aging_tally": aging_tally,
        "expired_tally": expired_tally,
        "lead_gate": lead_gate,
        "lead_count": lead_count,
        "lead_share_pct": lead_share_pct,
        "lead_margin": lead_margin,
        "lead_margin_severity": lead_margin_severity,
        "lead_runner_gate": lead_runner_gate,
        "lead_runner_count": lead_runner_count,
        "lead_runner_share_pct": lead_runner_share_pct,
        "lead_share_delta_pp": lead_share_delta_pp,
        "lead_share_delta_severity": lead_share_delta_severity,
        "lead_share_vs_delta": lead_share_vs_delta,
        "lead_share_vs_delta_ahead": lead_share_vs_delta_ahead,
        "lead_share_vs_delta_share": lead_share_vs_delta_share,
        "lead_band": lead_band if lead else "",
        "lead_bit": lead_bit,
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
    data_dir: Path | str | None = None,
    window_stats: dict[str, Any] | None = None,
    open_positions: int | None = None,
) -> dict[str, Any]:
    """Compact promote A/B window line (Phase A / portfolio AI; display only).

    Shows Window A/B trading-day progress and whether live promote matches the
    protocol (A = off, B = on). Window A also shows triple sample progress
    ``N/M fills`` · ``N/M sells`` beside days (portfolio AI + xang1234 —
    days alone mislead; sell progress tracks the ≥3 close floor). When fills
    exist, appends in-window fees / fee-adjusted net (realized − all fees) —
    honesty before Window B (gross sell P&L alone is not edge). While A is
    still running with a thin ledger, status is ``building sample``; with
    fills ok but sparse closes, ``building closes``. When fills+closes already
    meet floors but days are still short, status is
    ``sample ready · keep Window A`` (days still needed — portfolio AI
    multi-meter honesty). An all-buy ledger (``A open-only · 0 sells``) is
    not ready — fee-adjusted edge needs closed rounds. Sparse closes
    (``A thin closes · N sells <WINDOW_A_TARGET_SELLS``) are also not ready —
    one lucky SELL after many buys is a thin control. Newest in-window SELL
    age uses RyanJHamby fresh/aging/stale: fresh
    (``A fresh closes · last sell Nd``) and aging
    (``WINDOW_A_AGING_SELL_DAYS``) speak on the glance; stale
    (``WINDOW_A_MAX_SELL_STALE_DAYS``) blocks ready (staskh
    confirm-against-latest-closed). When closed rounds exist and in-window
    fees exceed realized sell P&L, ``A fee drag {mild|heavy|severe|total} ·
    net −€N · fees N×`` warns (portfolio AI fee-burn + xang1234 severity
    bands; prefers fee-adjusted net € + fees÷realized multiple when known) —
    does not block ready for B. When fees ≤ realized on closed rounds, the
    fees-ok triad speaks: ``A fees comfortable`` when fees÷realized &lt;
    ``WINDOW_A_FEES_COMFORTABLE_RATIO``; ``A fees ok`` in the mid band;
    ``A fees thin`` when ≥ ``WINDOW_A_FEES_THIN_RATIO`` (still ≤1×; warn;
    still ready for B) — portfolio AI quiet vs high + xang1234 speak-both-sides
    severity — display only. When closed rounds carry ``wins``/``losses``,
    close polarity speaks ``A all-win|mixed|all-loss · Nw/Nl``
    (portfolio AI Win·Lose + xang1234 speak-both-sides). Mixed closes add a
    lean triad: ``mostly wins`` / ``even`` / ``mostly losses``
    (``closes_polarity_lean`` = win_lean / even / loss_lean). ``all_loss``
    and mixed ``loss_lean`` warn only — do not block ready for B. When
    ``avg_win`` and ``avg_loss`` are both > 0, close payoff speaks
    ``A payoff [strong|thin] · N×`` (avg win ÷ avg loss) — portfolio AI
    + xang1234 severity (strong ≥2× · ok mid · thin <1× warn); count lean
    ≠ € lean; thin does not block ready for B. When avgs allow, close
    expectancy speaks ``A expectancy [strong|thin] · +€N`` / ``−€N``
    (win_rate·avg_win − loss_rate·avg_loss) — portfolio AI €/close after
    payoff; positive severity vs avg_loss (strong ≥0.5× · ok mid · thin
    <0.25× warn); neg + thin warn only; does not block ready for B.
    When both sides have positive gross €, close profit factor speaks
    ``A PF [strong|thin] · N×`` (gross wins ÷ gross losses; PF = profit
    factor) — portfolio AI + xang1234 severity (strong ≥2× · ok mid ·
    thin <1× warn); payoff is avg ratio, PF is total € ratio; thin does
    not block ready for B. When closed rounds carry wins/losses, close
    win rate speaks ``A win rate [strong|thin] · N%`` (wins ÷ decided;
    portfolio AI hit rate after polarity + xang1234 severity: strong ≥60%
    · ok mid · thin <40% warn) — count lean ≠ hit rate; thin does not
    block ready for B. When win rate and payoff are both known, WR vs
    breakeven speaks ``A WR [above|at|below] BE · N% vs M%`` (BE% =
    100/(1+payoff); portfolio AI edge after WR+payoff + xang1234 severity)
    — hit rate alone ≠ edge when payoff ≠ 1; ``below`` warns only (still
    ready for B). When win rate and payoff are both known, full Kelly
    speaks ``A Kelly [strong|thin|neg] · N%`` (f* = p − (1−p)/R) —
    portfolio AI size fraction after WR vs BE. WR vs BE ≠ the equity
    fraction the edge supports. Neg ≤0 and thin <5% warn only (still
    ready for B). The Kelly bit is full Kelly, not half and not the live
    sizer. When Kelly is known, half-Kelly vs the cash sizer speaks
    ``A half-Kelly vs sizer [under|match|over] · N% vs 10%`` (half of f*
    vs ~10% cash). ``under`` warns only (still ready for B). When Kelly
    is known, quarter-Kelly vs the soft name cap speaks
    ``A quarter-Kelly vs cap [under|match|over] · N% vs 30%`` (¼ of f*
    vs ~30% equity). Equal slot ≠ the single-name ceiling. ``under``
    warns only (still ready for B). When Kelly is known, one practical
    pick speaks ``A practical Kelly [half|quarter|sizer|none]`` — the
    largest fraction that fits the ~10% cash sizer (portfolio AI after
    the comparisons). ``half · cut`` and ``none`` warn only (still ready
    for B). When Kelly is known, sample size speaks
    ``A Kelly sample [thin|ok] · N closes`` (decided closes vs 10). A
    close floor of 3 sells is not a size sample. ``thin`` warns only
    (still ready for B). When closed rounds carry fee-adjusted net, net expectancy
    speaks ``A net expect [strong|thin] · +€N`` / ``−€N`` (net ÷ sells;
    portfolio AI after gross expectancy) — gross €/close ≠ fee-adjusted
    €/close; gross+ / net− warns ``fees eat edge``; neg/thin warn only
    (still ready for B). When gross and net expectancy are both known,
    fee take speaks ``A fee take [comfortable|thin] · €N/close``
    (gross − net) — portfolio AI after net expect; distinct from fee drag
    (total fees vs realized); thin ≥0.5× of gross warns only (still ready
    for B). When net expect and fee take are both > 0, net/fee multiple
    speaks ``A net/fee [strong|thin] · N×`` (net ÷ fee take) — portfolio AI
    after fee take; fee take € alone ≠ remaining edge multiples; thin <1×
    warns only (still ready for B). When Window A day target is met but fills stay
    under the protocol floor
    (``WINDOW_A_TARGET_FILLS``), status is ``A thin · N fills <M`` instead of
    ready. When day+fill targets are met but Ops knobs drift from protocol
    (max 5 / 24h / revolut_standard / regime·RS·breadth on / AI validate /
    multi-role on / scan ≥15m / trade ≥5m, or open names > 5), status is
    ``B blocked · …`` instead of ready. Calm ≠ edge; compose default-on still
    blocked until A/B verdict + calm gate. Not an entry gate.
    """
    from stock_checker.promote_ab import (
        format_window_a_aging_closes_bit,
        format_window_a_closes_expectancy_bit,
        format_window_a_closes_fee_take_bit,
        format_window_a_closes_half_kelly_bit,
        format_window_a_closes_half_kelly_cap_bit,
        format_window_a_closes_half_kelly_slot_bit,
        format_window_a_closes_kelly_bit,
        format_window_a_closes_net_expectancy_bit,
        format_window_a_closes_net_profit_factor_bit,
        format_window_a_closes_net_vs_fee_bit,
        format_window_a_closes_payoff_bit,
        format_window_a_closes_polarity_bit,
        format_window_a_closes_profit_factor_bit,
        format_window_a_closes_quarter_kelly_bit,
        format_window_a_closes_quarter_kelly_cap_bit,
        format_window_a_closes_quarter_kelly_slot_bit,
        format_window_a_closes_practical_kelly_bit,
        format_window_a_closes_kelly_sample_bit,
        format_window_a_closes_loss_streak_bit,
        format_window_a_closes_loss_streak_max_bit,
        format_window_a_closes_loss_streak_mean_bit,
        format_window_a_closes_loss_streak_median_bit,
        format_window_a_closes_loss_streak_min_bit,
        format_window_a_closes_loss_streak_stdev_bit,
        format_window_a_closes_loss_streak_cv_bit,
        format_window_a_closes_win_streak_bit,
        format_window_a_closes_win_streak_max_bit,
        format_window_a_closes_win_streak_mean_bit,
        format_window_a_closes_win_streak_median_bit,
        format_window_a_closes_win_streak_min_bit,
        format_window_a_closes_win_streak_stdev_bit,
        format_window_a_closes_win_streak_cv_bit,
        format_window_a_closes_exit_mix_bit,
        format_window_a_closes_exit_tp_share_bit,
        format_window_a_closes_exit_sl_share_bit,
        format_window_a_closes_exit_rot_share_bit,
        format_window_a_closes_exit_trim_share_bit,
        format_window_a_closes_exit_lead_bit,
        format_window_a_closes_exit_euro_lead_bit,
        format_window_a_closes_exit_euro_offset_bit,
        format_window_a_closes_exit_euro_gap_bit,
        format_window_a_closes_exit_euro_conc_bit,
        format_window_a_closes_exit_euro_count_skew_bit,
        format_window_a_closes_exit_euro_size_bit,
        format_window_a_closes_exit_euro_size_n_bit,
        format_window_a_closes_exit_euro_size_rest_n_bit,
        format_window_a_closes_exit_euro_size_sign_bit,
        format_window_a_closes_exit_euro_size_rest_sign_bit,
        format_window_a_closes_exit_euro_size_sign_clash_bit,
        format_window_a_closes_exit_euro_size_sign_clash_net_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit,
        format_window_a_closes_exit_unknown_bit,
        format_window_a_closes_flat_bit,
        format_window_a_closes_win_rate_bit,
        format_window_a_closes_wr_vs_be_bit,
        format_window_a_fee_drag_bit,
        format_window_a_fees_ok_bit,
        format_window_a_fill_progress_bit,
        format_window_a_fresh_closes_bit,
        format_window_a_open_only_bit,
        format_window_a_stale_closes_bit,
        format_window_a_thin_bit,
        format_window_a_thin_closes_bit,
        format_window_b_block_bit,
        format_window_stats_bit,
        promote_ab_snapshot,
        window_a_sample_readiness,
        window_b_readiness,
        window_stats_from_data_dir,
    )

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
        "window_stats": None,
        "window_stats_bit": "",
        "sample_ready": False,
        "sample_known": False,
        "sample_fills": 0,
        "target_fills": 0,
        "sample_buys": 0,
        "sample_sells": 0,
        "sample_open_only": False,
        "sample_thin_closes": False,
        "sample_stale_closes": False,
        "sample_aging_closes": False,
        "sample_fresh_closes": False,
        "closes_freshness": "",
        "sample_fee_drag": False,
        "fee_drag_severity": "",
        "sample_fees_ok": False,
        "fees_ok_severity": "",
        "closes_polarity": "",
        "closes_polarity_lean": "",
        "closes_all_loss": False,
        "closes_loss_lean": False,
        "closes_payoff_ratio": None,
        "closes_payoff_severity": "",
        "closes_payoff_thin": False,
        "closes_expectancy": None,
        "closes_expectancy_neg": False,
        "closes_expectancy_severity": "",
        "closes_expectancy_thin": False,
        "closes_expectancy_ratio": None,
        "closes_profit_factor": None,
        "closes_profit_factor_severity": "",
        "closes_profit_factor_thin": False,
        "closes_win_rate_pct": None,
        "closes_win_rate_severity": "",
        "closes_win_rate_thin": False,
        "closes_breakeven_wr_pct": None,
        "closes_wr_vs_be": "",
        "closes_wr_below_be": False,
        "closes_wr_edge_pp": None,
        "closes_wr_edge_severity": "",
        "closes_wr_edge_thin": False,
        "closes_kelly_pct": None,
        "closes_kelly_severity": "",
        "closes_kelly_thin": False,
        "closes_kelly_neg": False,
        "closes_half_kelly_pct": None,
        "closes_half_kelly_sizer_pct": None,
        "closes_half_kelly_vs": "",
        "closes_half_kelly_under": False,
        "closes_half_kelly_slot_pct": None,
        "closes_half_kelly_vs_slot": "",
        "closes_half_kelly_slot_under": False,
        "closes_half_kelly_cap_pct": None,
        "closes_half_kelly_vs_cap": "",
        "closes_half_kelly_cap_under": False,
        "closes_quarter_kelly_pct": None,
        "closes_quarter_kelly_sizer_pct": None,
        "closes_quarter_kelly_vs": "",
        "closes_quarter_kelly_under": False,
        "closes_quarter_kelly_slot_pct": None,
        "closes_quarter_kelly_vs_slot": "",
        "closes_quarter_kelly_slot_under": False,
        "closes_quarter_kelly_cap_pct": None,
        "closes_quarter_kelly_vs_cap": "",
        "closes_quarter_kelly_cap_under": False,
        "closes_practical_kelly": "",
        "closes_practical_kelly_pct": None,
        "closes_practical_kelly_cut": False,
        "closes_kelly_sample": "",
        "closes_kelly_sample_n": None,
        "closes_kelly_sample_thin": False,
        "closes_loss_streak": None,
        "closes_loss_streak_hot": False,
        "closes_loss_streak_max": None,
        "closes_loss_streak_max_hot": False,
        "closes_loss_streak_mean": None,
        "closes_loss_streak_runs": None,
        "closes_loss_streak_mean_hot": False,
        "closes_loss_streak_median": None,
        "closes_loss_streak_median_hot": False,
        "closes_loss_streak_min": None,
        "closes_loss_streak_min_hot": False,
        "closes_loss_streak_stdev": None,
        "closes_loss_streak_stdev_hot": False,
        "closes_loss_streak_cv": None,
        "closes_loss_streak_cv_hot": False,
        "closes_win_streak": None,
        "closes_win_streak_hot": False,
        "closes_win_streak_max": None,
        "closes_win_streak_max_hot": False,
        "closes_win_streak_mean": None,
        "closes_win_streak_runs": None,
        "closes_win_streak_mean_hot": False,
        "closes_win_streak_median": None,
        "closes_win_streak_median_hot": False,
        "closes_win_streak_min": None,
        "closes_win_streak_min_hot": False,
        "closes_win_streak_stdev": None,
        "closes_win_streak_stdev_hot": False,
        "closes_win_streak_cv": None,
        "closes_win_streak_cv_hot": False,
        "closes_flat": None,
        "closes_flat_warn": False,
        "closes_exit_tp": None,
        "closes_exit_sl": None,
        "closes_exit_rot": None,
        "closes_exit_trim": None,
        "closes_exit_mix_hot": False,
        "closes_exit_unknown": None,
        "closes_exit_unknown_warn": False,
        "closes_exit_tp_share_pct": None,
        "closes_exit_tp_share_severity": "",
        "closes_exit_tp_share_thin": False,
        "closes_exit_sl_share_pct": None,
        "closes_exit_sl_share_severity": "",
        "closes_exit_sl_share_hot": False,
        "closes_exit_rot_share_pct": None,
        "closes_exit_rot_share_severity": "",
        "closes_exit_rot_share_hot": False,
        "closes_exit_trim_share_pct": None,
        "closes_exit_trim_share_severity": "",
        "closes_exit_trim_share_hot": False,
        "closes_exit_lead": None,
        "closes_exit_lead_pct": None,
        "closes_exit_lead_hot": False,
        "closes_exit_euro_lead": None,
        "closes_exit_euro_pnl": None,
        "closes_exit_euro_lead_hot": False,
        "closes_exit_euro_offset": None,
        "closes_exit_euro_offset_pnl": None,
        "closes_exit_euro_offset_ratio": None,
        "closes_exit_euro_offset_hot": False,
        "closes_exit_euro_gap_ratio": None,
        "closes_exit_euro_gap_vs": None,
        "closes_exit_euro_gap_hot": False,
        "closes_exit_euro_conc": None,
        "closes_exit_euro_conc_pct": None,
        "closes_exit_euro_conc_hot": False,
        "closes_exit_euro_count_skew_pp": None,
        "closes_exit_euro_count_skew_hot": False,
        "closes_exit_euro_size_ratio": None,
        "closes_exit_euro_size_hot": False,
        "closes_exit_euro_size_n": "",
        "closes_exit_euro_size_n_count": None,
        "closes_exit_euro_size_n_thin": False,
        "closes_exit_euro_size_rest_n": "",
        "closes_exit_euro_size_rest_n_count": None,
        "closes_exit_euro_size_rest_n_thin": False,
        "closes_exit_euro_size_sign": "",
        "closes_exit_euro_size_sign_pnl": None,
        "closes_exit_euro_size_sign_loss": False,
        "closes_exit_euro_size_rest_sign": "",
        "closes_exit_euro_size_rest_sign_pnl": None,
        "closes_exit_euro_size_rest_sign_loss": False,
        "closes_exit_euro_size_sign_clash": "",
        "closes_exit_euro_size_sign_clash_loss": False,
        "closes_exit_euro_size_sign_clash_net": "",
        "closes_exit_euro_size_sign_clash_net_pnl": None,
        "closes_exit_euro_size_sign_clash_net_loss": False,
        "closes_exit_euro_size_sign_clash_keep": "",
        "closes_exit_euro_size_sign_clash_keep_ratio": None,
        "closes_exit_euro_size_sign_clash_keep_thin": False,
        "closes_exit_euro_size_sign_clash_keep_fees": "",
        "closes_exit_euro_size_sign_clash_keep_fees_ratio": None,
        "closes_exit_euro_size_sign_clash_keep_fees_warn": False,
        "closes_exit_euro_size_sign_clash_keep_fees_vs": "",
        "closes_exit_euro_size_sign_clash_keep_fees_vs_window": "",
        "closes_exit_euro_size_sign_clash_keep_fees_vs_warn": False,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap": "",
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_ratio": None,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_warn": False,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir": "",
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_ratio": None,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_warn": False,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_leftover": None,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_window": None,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_warn": False,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta": "",
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_ratio": None,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_warn": False,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_leftover": None,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_window": None,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_warn": False,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta": "",
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_ratio": None,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_warn": False,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta": "",
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_warn": False,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align": "",
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_warn": False,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size": "",
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size_warn": False,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead": "",
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_warn": False,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size": "",
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_ratio": None,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_warn": False,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_louder": None,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_quieter": None,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_warn": False,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta": "",
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_ratio": None,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_warn": False,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_louder_pct": None,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_quieter_pct": None,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_warn": False,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta": "",
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_ratio": None,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_warn": False,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta": "",
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_warn": False,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align": "",
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_warn": False,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size": "",
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size_warn": False,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead": "",
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_warn": False,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size": "",
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_warn": False,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_warn": False,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_warn": False,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_warn": False,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta_warn": False,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta": "",
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_warn": False,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align": "",
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_warn": False,
        "closes_net_expectancy": None,
        "closes_net_expectancy_neg": False,
        "closes_net_expectancy_severity": "",
        "closes_net_expectancy_thin": False,
        "closes_net_expectancy_ratio": None,
        "closes_net_expectancy_eats_edge": False,
        "closes_fee_take": None,
        "closes_fee_take_severity": "",
        "closes_fee_take_thin": False,
        "closes_fee_take_ratio": None,
        "closes_net_vs_fee": None,
        "closes_net_vs_fee_severity": "",
        "closes_net_vs_fee_thin": False,
        "closes_net_profit_factor": None,
        "closes_net_profit_factor_severity": "",
        "closes_net_profit_factor_thin": False,
        "closes_net_profit_factor_eats_edge": False,
        "a_fill_progress_bit": "",
        "a_thin_bit": "",
        "a_open_only_bit": "",
        "a_thin_closes_bit": "",
        "a_stale_closes_bit": "",
        "a_aging_closes_bit": "",
        "a_fresh_closes_bit": "",
        "a_fee_drag_bit": "",
        "a_fees_ok_bit": "",
        "a_closes_polarity_bit": "",
        "a_closes_win_rate_bit": "",
        "a_closes_wr_vs_be_bit": "",
        "a_closes_kelly_bit": "",
        "a_closes_half_kelly_bit": "",
        "a_closes_half_kelly_slot_bit": "",
        "a_closes_half_kelly_cap_bit": "",
        "a_closes_quarter_kelly_bit": "",
        "a_closes_quarter_kelly_slot_bit": "",
        "a_closes_quarter_kelly_cap_bit": "",
        "a_closes_practical_kelly_bit": "",
        "a_closes_kelly_sample_bit": "",
        "a_closes_loss_streak_bit": "",
        "a_closes_loss_streak_max_bit": "",
        "a_closes_loss_streak_mean_bit": "",
        "a_closes_loss_streak_median_bit": "",
        "a_closes_loss_streak_min_bit": "",
        "a_closes_loss_streak_stdev_bit": "",
        "a_closes_loss_streak_cv_bit": "",
        "a_closes_win_streak_bit": "",
        "a_closes_win_streak_max_bit": "",
        "a_closes_win_streak_mean_bit": "",
        "a_closes_win_streak_median_bit": "",
        "a_closes_win_streak_min_bit": "",
        "a_closes_win_streak_stdev_bit": "",
        "a_closes_win_streak_cv_bit": "",
        "a_closes_exit_mix_bit": "",
        "a_closes_exit_tp_share_bit": "",
        "a_closes_exit_sl_share_bit": "",
        "a_closes_exit_rot_share_bit": "",
        "a_closes_exit_trim_share_bit": "",
        "a_closes_exit_lead_bit": "",
        "a_closes_exit_euro_lead_bit": "",
        "a_closes_exit_euro_offset_bit": "",
        "a_closes_exit_euro_gap_bit": "",
        "a_closes_exit_euro_conc_bit": "",
        "a_closes_exit_euro_count_skew_bit": "",
        "a_closes_exit_euro_size_bit": "",
        "a_closes_exit_euro_size_n_bit": "",
        "a_closes_exit_euro_size_rest_n_bit": "",
        "a_closes_exit_euro_size_sign_bit": "",
        "a_closes_exit_euro_size_rest_sign_bit": "",
        "a_closes_exit_euro_size_sign_clash_bit": "",
        "a_closes_exit_euro_size_sign_clash_net_bit": "",
        "a_closes_exit_euro_size_sign_clash_keep_bit": "",
        "a_closes_exit_euro_size_sign_clash_keep_fees_bit": "",
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_bit": "",
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_bit": "",
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_bit": "",
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_bit": "",
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_bit": "",
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit": "",
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_bit": "",
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_bit": "",
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_bit": "",
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size_bit": "",
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_bit": "",
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_bit": "",
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_bit": "",
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_bit": "",
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_bit": "",
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_bit": "",
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_bit": "",
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit": "",
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size_bit": "",
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_bit": "",
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_bit": "",
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_bit": "",
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_bit": "",
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_bit": "",
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta_bit": "",
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_bit": "",
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit": "",
        "a_closes_exit_unknown_bit": "",
        "a_closes_flat_bit": "",
        "a_closes_payoff_bit": "",
        "a_closes_expectancy_bit": "",
        "a_closes_net_expectancy_bit": "",
        "a_closes_fee_take_bit": "",
        "a_closes_net_vs_fee_bit": "",
        "a_closes_net_profit_factor_bit": "",
        "a_closes_profit_factor_bit": "",
        "b_ready": False,
        "b_blockers": [],
        "b_block_bit": "",
    }
    if not isinstance(runtime, dict):
        return empty
    promote_on = bool(runtime.get("promote_experiment_strategy"))
    as_of_day = as_of or date.today()
    snap = promote_ab_snapshot(promote_on, as_of=as_of_day)
    window = str(snap.get("window") or "A")
    days = int(snap.get("trading_days") or 0)
    need = int(snap.get("target_days") or 10)
    target_met = bool(snap.get("target_met"))
    protocol_ok = bool(snap.get("protocol_ok"))
    promote_label = "on" if promote_on else "off"
    stats = window_stats
    if stats is None and data_dir is not None:
        stats = window_stats_from_data_dir(data_dir, promote_on=promote_on)
    max_pos_raw = runtime.get("max_positions")
    max_pos = int(max_pos_raw) if max_pos_raw is not None else None
    open_n = open_positions
    if open_n is None and runtime.get("open_positions") is not None:
        open_n = int(runtime.get("open_positions") or 0)
    hold_raw = runtime.get("min_hold_hours")
    hold_h = float(hold_raw) if hold_raw is not None else None
    fee_raw = runtime.get("fee_preset")
    fee_preset = str(fee_raw).strip().lower() if fee_raw is not None else None

    def _opt_bool(key: str) -> bool | None:
        if key not in runtime or runtime.get(key) is None:
            return None
        return bool(runtime.get(key))

    ai_raw = runtime.get("ai_mode")
    ai_mode = str(ai_raw).strip().lower() if ai_raw is not None else None
    scan_raw = runtime.get("scan_interval_min")
    scan_m = int(scan_raw) if scan_raw is not None else None
    trade_raw = runtime.get("trade_interval_min")
    trade_m = int(trade_raw) if trade_raw is not None else None
    b_ready_info = window_b_readiness(
        max_positions=max_pos,
        open_positions=open_n,
        min_hold_hours=hold_h,
        fee_preset=fee_preset,
        regime_gate=_opt_bool("regime_gate"),
        rs_gate=_opt_bool("rs_gate"),
        breadth_gate=_opt_bool("breadth_gate"),
        ai_mode=ai_mode,
        ai_multi_role=_opt_bool("ai_multi_role"),
        scan_interval_min=scan_m,
        trade_interval_min=trade_m,
    )
    b_blockers = list(b_ready_info.get("blockers") or [])
    b_block_bit = format_window_b_block_bit(b_blockers)
    b_knobs_ready = bool(b_ready_info.get("ready"))
    sample = window_a_sample_readiness(
        stats if window == "A" else None, as_of=as_of_day
    )
    sample_ready = bool(sample.get("ready"))
    sample_known = bool(sample.get("known"))
    sample_fills = int(sample.get("fills") or 0)
    target_fills = int(sample.get("target_fills") or 0)
    sample_buys = int(sample.get("buys") or 0)
    sample_sells = int(sample.get("sells") or 0)
    sample_open_only = bool(sample.get("open_only"))
    sample_thin_closes = bool(sample.get("thin_closes"))
    sample_stale_closes = bool(sample.get("stale_closes"))
    sample_aging_closes = bool(sample.get("aging_closes"))
    sample_fresh_closes = bool(sample.get("fresh_closes"))
    closes_freshness = str(sample.get("closes_freshness") or "")
    sample_fee_drag = bool(sample.get("fee_drag"))
    fee_drag_severity = str(sample.get("fee_drag_severity") or "")
    sample_fees_ok = bool(sample.get("fees_ok"))
    fees_ok_severity = str(sample.get("fees_ok_severity") or "")
    fees_thin = fees_ok_severity == "thin"
    closes_polarity = str(sample.get("closes_polarity") or "")
    closes_polarity_lean = str(sample.get("closes_polarity_lean") or "")
    closes_all_loss = bool(sample.get("closes_all_loss"))
    closes_loss_lean = bool(sample.get("closes_loss_lean"))
    closes_payoff_ratio = sample.get("closes_payoff_ratio")
    closes_payoff_severity = str(sample.get("closes_payoff_severity") or "")
    closes_payoff_thin = bool(sample.get("closes_payoff_thin"))
    closes_expectancy = sample.get("closes_expectancy")
    closes_expectancy_neg = bool(sample.get("closes_expectancy_neg"))
    closes_expectancy_severity = str(sample.get("closes_expectancy_severity") or "")
    closes_expectancy_thin = bool(sample.get("closes_expectancy_thin"))
    closes_expectancy_ratio = sample.get("closes_expectancy_ratio")
    closes_profit_factor = sample.get("closes_profit_factor")
    closes_profit_factor_severity = str(sample.get("closes_profit_factor_severity") or "")
    closes_profit_factor_thin = bool(sample.get("closes_profit_factor_thin"))
    closes_win_rate_pct = sample.get("closes_win_rate_pct")
    closes_win_rate_severity = str(sample.get("closes_win_rate_severity") or "")
    closes_win_rate_thin = bool(sample.get("closes_win_rate_thin"))
    closes_breakeven_wr_pct = sample.get("closes_breakeven_wr_pct")
    closes_wr_vs_be = str(sample.get("closes_wr_vs_be") or "")
    closes_wr_below_be = bool(sample.get("closes_wr_below_be"))
    closes_wr_edge_pp = sample.get("closes_wr_edge_pp")
    closes_wr_edge_severity = str(sample.get("closes_wr_edge_severity") or "")
    closes_wr_edge_thin = bool(sample.get("closes_wr_edge_thin"))
    closes_kelly_pct = sample.get("closes_kelly_pct")
    closes_kelly_severity = str(sample.get("closes_kelly_severity") or "")
    closes_kelly_thin = bool(sample.get("closes_kelly_thin"))
    closes_kelly_neg = bool(sample.get("closes_kelly_neg"))
    closes_half_kelly_pct = sample.get("closes_half_kelly_pct")
    closes_half_kelly_sizer_pct = sample.get("closes_half_kelly_sizer_pct")
    closes_half_kelly_vs = str(sample.get("closes_half_kelly_vs") or "")
    closes_half_kelly_under = bool(sample.get("closes_half_kelly_under"))
    closes_half_kelly_slot_pct = sample.get("closes_half_kelly_slot_pct")
    closes_half_kelly_vs_slot = str(sample.get("closes_half_kelly_vs_slot") or "")
    closes_half_kelly_slot_under = bool(sample.get("closes_half_kelly_slot_under"))
    closes_half_kelly_cap_pct = sample.get("closes_half_kelly_cap_pct")
    closes_half_kelly_vs_cap = str(sample.get("closes_half_kelly_vs_cap") or "")
    closes_half_kelly_cap_under = bool(sample.get("closes_half_kelly_cap_under"))
    closes_quarter_kelly_pct = sample.get("closes_quarter_kelly_pct")
    closes_quarter_kelly_sizer_pct = sample.get("closes_quarter_kelly_sizer_pct")
    closes_quarter_kelly_vs = str(sample.get("closes_quarter_kelly_vs") or "")
    closes_quarter_kelly_under = bool(sample.get("closes_quarter_kelly_under"))
    closes_quarter_kelly_slot_pct = sample.get("closes_quarter_kelly_slot_pct")
    closes_quarter_kelly_vs_slot = str(
        sample.get("closes_quarter_kelly_vs_slot") or ""
    )
    closes_quarter_kelly_slot_under = bool(
        sample.get("closes_quarter_kelly_slot_under")
    )
    closes_quarter_kelly_cap_pct = sample.get("closes_quarter_kelly_cap_pct")
    closes_quarter_kelly_vs_cap = str(
        sample.get("closes_quarter_kelly_vs_cap") or ""
    )
    closes_quarter_kelly_cap_under = bool(
        sample.get("closes_quarter_kelly_cap_under")
    )
    closes_practical_kelly = str(sample.get("closes_practical_kelly") or "")
    closes_practical_kelly_pct = sample.get("closes_practical_kelly_pct")
    closes_practical_kelly_cut = bool(sample.get("closes_practical_kelly_cut"))
    closes_kelly_sample = str(sample.get("closes_kelly_sample") or "")
    closes_kelly_sample_n = sample.get("closes_kelly_sample_n")
    closes_kelly_sample_thin = bool(sample.get("closes_kelly_sample_thin"))
    closes_loss_streak = sample.get("closes_loss_streak")
    closes_loss_streak_hot = bool(sample.get("closes_loss_streak_hot"))
    closes_loss_streak_max = sample.get("closes_loss_streak_max")
    closes_loss_streak_max_hot = bool(sample.get("closes_loss_streak_max_hot"))
    closes_loss_streak_mean = sample.get("closes_loss_streak_mean")
    closes_loss_streak_runs = sample.get("closes_loss_streak_runs")
    closes_loss_streak_mean_hot = bool(sample.get("closes_loss_streak_mean_hot"))
    closes_loss_streak_median = sample.get("closes_loss_streak_median")
    closes_loss_streak_median_hot = bool(
        sample.get("closes_loss_streak_median_hot")
    )
    closes_loss_streak_min = sample.get("closes_loss_streak_min")
    closes_loss_streak_min_hot = bool(sample.get("closes_loss_streak_min_hot"))
    closes_loss_streak_stdev = sample.get("closes_loss_streak_stdev")
    closes_loss_streak_stdev_hot = bool(sample.get("closes_loss_streak_stdev_hot"))
    closes_loss_streak_cv = sample.get("closes_loss_streak_cv")
    closes_loss_streak_cv_hot = bool(sample.get("closes_loss_streak_cv_hot"))
    closes_win_streak = sample.get("closes_win_streak")
    closes_win_streak_hot = bool(sample.get("closes_win_streak_hot"))
    closes_win_streak_max = sample.get("closes_win_streak_max")
    closes_win_streak_max_hot = bool(sample.get("closes_win_streak_max_hot"))
    closes_win_streak_mean = sample.get("closes_win_streak_mean")
    closes_win_streak_runs = sample.get("closes_win_streak_runs")
    closes_win_streak_mean_hot = bool(sample.get("closes_win_streak_mean_hot"))
    closes_win_streak_median = sample.get("closes_win_streak_median")
    closes_win_streak_median_hot = bool(
        sample.get("closes_win_streak_median_hot")
    )
    closes_win_streak_min = sample.get("closes_win_streak_min")
    closes_win_streak_min_hot = bool(sample.get("closes_win_streak_min_hot"))
    closes_win_streak_stdev = sample.get("closes_win_streak_stdev")
    closes_win_streak_stdev_hot = bool(sample.get("closes_win_streak_stdev_hot"))
    closes_win_streak_cv = sample.get("closes_win_streak_cv")
    closes_win_streak_cv_hot = bool(sample.get("closes_win_streak_cv_hot"))
    closes_flat = sample.get("closes_flat")
    closes_flat_warn = bool(sample.get("closes_flat_warn"))
    closes_exit_tp = sample.get("closes_exit_tp")
    closes_exit_sl = sample.get("closes_exit_sl")
    closes_exit_rot = sample.get("closes_exit_rot")
    closes_exit_trim = sample.get("closes_exit_trim")
    closes_exit_mix_hot = bool(sample.get("closes_exit_mix_hot"))
    closes_exit_unknown = sample.get("closes_exit_unknown")
    closes_exit_unknown_warn = bool(sample.get("closes_exit_unknown_warn"))
    closes_exit_tp_share_pct = sample.get("closes_exit_tp_share_pct")
    closes_exit_tp_share_severity = str(
        sample.get("closes_exit_tp_share_severity") or ""
    )
    closes_exit_tp_share_thin = bool(sample.get("closes_exit_tp_share_thin"))
    closes_exit_sl_share_pct = sample.get("closes_exit_sl_share_pct")
    closes_exit_sl_share_severity = str(
        sample.get("closes_exit_sl_share_severity") or ""
    )
    closes_exit_sl_share_hot = bool(sample.get("closes_exit_sl_share_hot"))
    closes_exit_rot_share_pct = sample.get("closes_exit_rot_share_pct")
    closes_exit_rot_share_severity = str(
        sample.get("closes_exit_rot_share_severity") or ""
    )
    closes_exit_rot_share_hot = bool(sample.get("closes_exit_rot_share_hot"))
    closes_exit_trim_share_pct = sample.get("closes_exit_trim_share_pct")
    closes_exit_trim_share_severity = str(
        sample.get("closes_exit_trim_share_severity") or ""
    )
    closes_exit_trim_share_hot = bool(sample.get("closes_exit_trim_share_hot"))
    closes_exit_lead = sample.get("closes_exit_lead")
    closes_exit_lead_pct = sample.get("closes_exit_lead_pct")
    closes_exit_lead_hot = bool(sample.get("closes_exit_lead_hot"))
    closes_exit_euro_lead = sample.get("closes_exit_euro_lead")
    closes_exit_euro_pnl = sample.get("closes_exit_euro_pnl")
    closes_exit_euro_lead_hot = bool(sample.get("closes_exit_euro_lead_hot"))
    closes_exit_euro_offset = sample.get("closes_exit_euro_offset")
    closes_exit_euro_offset_pnl = sample.get("closes_exit_euro_offset_pnl")
    closes_exit_euro_offset_ratio = sample.get("closes_exit_euro_offset_ratio")
    closes_exit_euro_offset_hot = bool(sample.get("closes_exit_euro_offset_hot"))
    closes_exit_euro_gap_ratio = sample.get("closes_exit_euro_gap_ratio")
    closes_exit_euro_gap_vs = sample.get("closes_exit_euro_gap_vs")
    closes_exit_euro_gap_hot = bool(sample.get("closes_exit_euro_gap_hot"))
    closes_exit_euro_conc = sample.get("closes_exit_euro_conc")
    closes_exit_euro_conc_pct = sample.get("closes_exit_euro_conc_pct")
    closes_exit_euro_conc_hot = bool(sample.get("closes_exit_euro_conc_hot"))
    closes_exit_euro_count_skew_pp = sample.get("closes_exit_euro_count_skew_pp")
    closes_exit_euro_count_skew_hot = bool(
        sample.get("closes_exit_euro_count_skew_hot")
    )
    closes_exit_euro_size_ratio = sample.get("closes_exit_euro_size_ratio")
    closes_exit_euro_size_hot = bool(sample.get("closes_exit_euro_size_hot"))
    closes_exit_euro_size_n = str(sample.get("closes_exit_euro_size_n") or "")
    closes_exit_euro_size_n_count = sample.get("closes_exit_euro_size_n_count")
    closes_exit_euro_size_n_thin = bool(
        sample.get("closes_exit_euro_size_n_thin")
    )
    closes_exit_euro_size_rest_n = str(
        sample.get("closes_exit_euro_size_rest_n") or ""
    )
    closes_exit_euro_size_rest_n_count = sample.get(
        "closes_exit_euro_size_rest_n_count"
    )
    closes_exit_euro_size_rest_n_thin = bool(
        sample.get("closes_exit_euro_size_rest_n_thin")
    )
    closes_exit_euro_size_sign = str(
        sample.get("closes_exit_euro_size_sign") or ""
    )
    closes_exit_euro_size_sign_pnl = sample.get("closes_exit_euro_size_sign_pnl")
    closes_exit_euro_size_sign_loss = bool(
        sample.get("closes_exit_euro_size_sign_loss")
    )
    closes_exit_euro_size_rest_sign = str(
        sample.get("closes_exit_euro_size_rest_sign") or ""
    )
    closes_exit_euro_size_rest_sign_pnl = sample.get(
        "closes_exit_euro_size_rest_sign_pnl"
    )
    closes_exit_euro_size_rest_sign_loss = bool(
        sample.get("closes_exit_euro_size_rest_sign_loss")
    )
    closes_exit_euro_size_sign_clash = str(
        sample.get("closes_exit_euro_size_sign_clash") or ""
    )
    closes_exit_euro_size_sign_clash_loss = bool(
        sample.get("closes_exit_euro_size_sign_clash_loss")
    )
    closes_exit_euro_size_sign_clash_net = str(
        sample.get("closes_exit_euro_size_sign_clash_net") or ""
    )
    closes_exit_euro_size_sign_clash_net_pnl = sample.get(
        "closes_exit_euro_size_sign_clash_net_pnl"
    )
    closes_exit_euro_size_sign_clash_net_loss = bool(
        sample.get("closes_exit_euro_size_sign_clash_net_loss")
    )
    closes_exit_euro_size_sign_clash_keep = str(
        sample.get("closes_exit_euro_size_sign_clash_keep") or ""
    )
    closes_exit_euro_size_sign_clash_keep_ratio = sample.get(
        "closes_exit_euro_size_sign_clash_keep_ratio"
    )
    closes_exit_euro_size_sign_clash_keep_thin = bool(
        sample.get("closes_exit_euro_size_sign_clash_keep_thin")
    )
    closes_exit_euro_size_sign_clash_keep_fees = str(
        sample.get("closes_exit_euro_size_sign_clash_keep_fees") or ""
    )
    closes_exit_euro_size_sign_clash_keep_fees_ratio = sample.get(
        "closes_exit_euro_size_sign_clash_keep_fees_ratio"
    )
    closes_exit_euro_size_sign_clash_keep_fees_warn = bool(
        sample.get("closes_exit_euro_size_sign_clash_keep_fees_warn")
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs = str(
        sample.get("closes_exit_euro_size_sign_clash_keep_fees_vs") or ""
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_window = str(
        sample.get("closes_exit_euro_size_sign_clash_keep_fees_vs_window") or ""
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_warn = bool(
        sample.get("closes_exit_euro_size_sign_clash_keep_fees_vs_warn")
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap = str(
        sample.get("closes_exit_euro_size_sign_clash_keep_fees_vs_gap") or ""
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_ratio = sample.get(
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_ratio"
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_warn = bool(
        sample.get("closes_exit_euro_size_sign_clash_keep_fees_vs_gap_warn")
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir = str(
        sample.get("closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir") or ""
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_ratio = sample.get(
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_ratio"
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_warn = bool(
        sample.get("closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_warn")
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_leftover = sample.get(
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_leftover"
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_window = sample.get(
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_window"
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_warn = bool(
        sample.get("closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_warn")
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta = str(
        sample.get("closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta")
        or ""
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_ratio = sample.get(
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_ratio"
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_warn = bool(
        sample.get(
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_warn"
        )
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_leftover = (
        sample.get(
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_leftover"
        )
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_window = (
        sample.get(
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_window"
        )
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_warn = bool(
        sample.get(
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_warn"
        )
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta = str(
        sample.get(
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta"
        )
        or ""
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_ratio = (
        sample.get(
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_ratio"
        )
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_warn = bool(
        sample.get(
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_warn"
        )
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta = str(
        sample.get(
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta"
        )
        or ""
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_warn = (
        bool(
            sample.get(
                "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_warn"
            )
        )
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align = (
        str(
            sample.get(
                "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align"
            )
            or ""
        )
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_warn = (
        bool(
            sample.get(
                "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_warn"
            )
        )
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size = (
        str(
            sample.get(
                "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size"
            )
            or ""
        )
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size_warn = (
        bool(
            sample.get(
                "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size_warn"
            )
        )
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead = (
        str(
            sample.get(
                "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead"
            )
            or ""
        )
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_warn = (
        bool(
            sample.get(
                "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_warn"
            )
        )
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size = (
        str(
            sample.get(
                "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size"
            )
            or ""
        )
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_warn = (
        bool(
            sample.get(
                "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_warn"
            )
        )
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_louder = (
        sample.get(
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_louder"
        )
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_quieter = (
        sample.get(
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_quieter"
        )
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_warn = (
        bool(
            sample.get(
                "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_warn"
            )
        )
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta = (
        str(
            sample.get(
                "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta"
            )
            or ""
        )
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_ratio = (
        sample.get(
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_ratio"
        )
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_warn = (
        bool(
            sample.get(
                "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_warn"
            )
        )
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_louder_pct = (
        sample.get(
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_louder_pct"
        )
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_quieter_pct = (
        sample.get(
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_quieter_pct"
        )
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_warn = (
        bool(
            sample.get(
                "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_warn"
            )
        )
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta = str(
        sample.get(
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta"
        )
        or ""
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_ratio = (
        sample.get(
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_ratio"
        )
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_warn = (
        bool(
            sample.get(
                "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_warn"
            )
        )
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta = str(
        sample.get(
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta"
        )
        or ""
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_warn = (
        bool(
            sample.get(
                "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_warn"
            )
        )
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align = str(
        sample.get(
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align"
        )
        or ""
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_warn = (
        bool(
            sample.get(
                "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_warn"
            )
        )
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size = str(
        sample.get(
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size"
        )
        or ""
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size_warn = (
        bool(
            sample.get(
                "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size_warn"
            )
        )
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead = str(
        sample.get(
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead"
        )
        or ""
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_warn = (
        bool(
            sample.get(
                "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_warn"
            )
        )
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size = str(
        sample.get(
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size"
        )
        or ""
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_warn = (
        bool(
            sample.get(
                "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_warn"
            )
        )
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_warn = (
        bool(
            sample.get(
                "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_warn"
            )
        )
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_warn = (
        bool(
            sample.get(
                "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_warn"
            )
        )
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_warn = (
        bool(
            sample.get(
                "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_warn"
            )
        )
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta_warn = (
        bool(
            sample.get(
                "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta_warn"
            )
        )
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta = str(
        sample.get(
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta"
        )
        or ""
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_warn = (
        bool(
            sample.get(
                "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_warn"
            )
        )
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align = str(
        sample.get(
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align"
        )
        or ""
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_warn = (
        bool(
            sample.get(
                "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_warn"
            )
        )
    )
    closes_net_expectancy = sample.get("closes_net_expectancy")
    closes_net_expectancy_neg = bool(sample.get("closes_net_expectancy_neg"))
    closes_net_expectancy_severity = str(
        sample.get("closes_net_expectancy_severity") or ""
    )
    closes_net_expectancy_thin = bool(sample.get("closes_net_expectancy_thin"))
    closes_net_expectancy_ratio = sample.get("closes_net_expectancy_ratio")
    closes_net_expectancy_eats_edge = bool(
        sample.get("closes_net_expectancy_eats_edge")
    )
    closes_fee_take = sample.get("closes_fee_take")
    closes_fee_take_severity = str(sample.get("closes_fee_take_severity") or "")
    closes_fee_take_thin = bool(sample.get("closes_fee_take_thin"))
    closes_fee_take_ratio = sample.get("closes_fee_take_ratio")
    closes_net_vs_fee = sample.get("closes_net_vs_fee")
    closes_net_vs_fee_severity = str(sample.get("closes_net_vs_fee_severity") or "")
    closes_net_vs_fee_thin = bool(sample.get("closes_net_vs_fee_thin"))
    closes_net_profit_factor = sample.get("closes_net_profit_factor")
    closes_net_profit_factor_severity = str(
        sample.get("closes_net_profit_factor_severity") or ""
    )
    closes_net_profit_factor_thin = bool(sample.get("closes_net_profit_factor_thin"))
    closes_net_profit_factor_eats_edge = bool(
        sample.get("closes_net_profit_factor_eats_edge")
    )
    a_fill_progress_bit = (
        format_window_a_fill_progress_bit(sample) if window == "A" else ""
    )
    a_thin_bit = format_window_a_thin_bit(sample) if window == "A" else ""
    a_open_only_bit = (
        format_window_a_open_only_bit(sample) if window == "A" else ""
    )
    a_thin_closes_bit = (
        format_window_a_thin_closes_bit(sample) if window == "A" else ""
    )
    a_stale_closes_bit = (
        format_window_a_stale_closes_bit(sample) if window == "A" else ""
    )
    a_aging_closes_bit = (
        format_window_a_aging_closes_bit(sample) if window == "A" else ""
    )
    a_fresh_closes_bit = (
        format_window_a_fresh_closes_bit(sample) if window == "A" else ""
    )
    a_fee_drag_bit = (
        format_window_a_fee_drag_bit(sample) if window == "A" else ""
    )
    a_fees_ok_bit = (
        format_window_a_fees_ok_bit(sample) if window == "A" else ""
    )
    # Fee drag and fees ok are mutually exclusive; one status fee bit.
    a_fee_status_bit = a_fee_drag_bit or a_fees_ok_bit
    a_closes_polarity_bit = (
        format_window_a_closes_polarity_bit(sample) if window == "A" else ""
    )
    a_closes_win_rate_bit = (
        format_window_a_closes_win_rate_bit(sample) if window == "A" else ""
    )
    a_closes_wr_vs_be_bit = (
        format_window_a_closes_wr_vs_be_bit(sample) if window == "A" else ""
    )
    a_closes_kelly_bit = (
        format_window_a_closes_kelly_bit(sample) if window == "A" else ""
    )
    a_closes_half_kelly_bit = (
        format_window_a_closes_half_kelly_bit(sample) if window == "A" else ""
    )
    a_closes_half_kelly_slot_bit = (
        format_window_a_closes_half_kelly_slot_bit(sample)
        if window == "A"
        else ""
    )
    a_closes_half_kelly_cap_bit = (
        format_window_a_closes_half_kelly_cap_bit(sample)
        if window == "A"
        else ""
    )
    a_closes_quarter_kelly_bit = (
        format_window_a_closes_quarter_kelly_bit(sample)
        if window == "A"
        else ""
    )
    a_closes_quarter_kelly_slot_bit = (
        format_window_a_closes_quarter_kelly_slot_bit(sample)
        if window == "A"
        else ""
    )
    a_closes_quarter_kelly_cap_bit = (
        format_window_a_closes_quarter_kelly_cap_bit(sample)
        if window == "A"
        else ""
    )
    a_closes_practical_kelly_bit = (
        format_window_a_closes_practical_kelly_bit(sample)
        if window == "A"
        else ""
    )
    a_closes_kelly_sample_bit = (
        format_window_a_closes_kelly_sample_bit(sample)
        if window == "A"
        else ""
    )
    a_closes_loss_streak_bit = (
        format_window_a_closes_loss_streak_bit(sample) if window == "A" else ""
    )
    a_closes_loss_streak_max_bit = (
        format_window_a_closes_loss_streak_max_bit(sample)
        if window == "A"
        else ""
    )
    a_closes_loss_streak_mean_bit = (
        format_window_a_closes_loss_streak_mean_bit(sample)
        if window == "A"
        else ""
    )
    a_closes_loss_streak_median_bit = (
        format_window_a_closes_loss_streak_median_bit(sample)
        if window == "A"
        else ""
    )
    a_closes_loss_streak_min_bit = (
        format_window_a_closes_loss_streak_min_bit(sample)
        if window == "A"
        else ""
    )
    a_closes_loss_streak_stdev_bit = (
        format_window_a_closes_loss_streak_stdev_bit(sample)
        if window == "A"
        else ""
    )
    a_closes_loss_streak_cv_bit = (
        format_window_a_closes_loss_streak_cv_bit(sample)
        if window == "A"
        else ""
    )
    a_closes_win_streak_bit = (
        format_window_a_closes_win_streak_bit(sample) if window == "A" else ""
    )
    a_closes_win_streak_max_bit = (
        format_window_a_closes_win_streak_max_bit(sample)
        if window == "A"
        else ""
    )
    a_closes_win_streak_mean_bit = (
        format_window_a_closes_win_streak_mean_bit(sample)
        if window == "A"
        else ""
    )
    a_closes_win_streak_median_bit = (
        format_window_a_closes_win_streak_median_bit(sample)
        if window == "A"
        else ""
    )
    a_closes_win_streak_min_bit = (
        format_window_a_closes_win_streak_min_bit(sample)
        if window == "A"
        else ""
    )
    a_closes_win_streak_stdev_bit = (
        format_window_a_closes_win_streak_stdev_bit(sample)
        if window == "A"
        else ""
    )
    a_closes_win_streak_cv_bit = (
        format_window_a_closes_win_streak_cv_bit(sample)
        if window == "A"
        else ""
    )
    a_closes_exit_mix_bit = (
        format_window_a_closes_exit_mix_bit(sample) if window == "A" else ""
    )
    a_closes_exit_tp_share_bit = (
        format_window_a_closes_exit_tp_share_bit(sample) if window == "A" else ""
    )
    a_closes_exit_sl_share_bit = (
        format_window_a_closes_exit_sl_share_bit(sample) if window == "A" else ""
    )
    a_closes_exit_rot_share_bit = (
        format_window_a_closes_exit_rot_share_bit(sample) if window == "A" else ""
    )
    a_closes_exit_trim_share_bit = (
        format_window_a_closes_exit_trim_share_bit(sample) if window == "A" else ""
    )
    a_closes_exit_lead_bit = (
        format_window_a_closes_exit_lead_bit(sample) if window == "A" else ""
    )
    a_closes_exit_euro_lead_bit = (
        format_window_a_closes_exit_euro_lead_bit(sample) if window == "A" else ""
    )
    a_closes_exit_euro_offset_bit = (
        format_window_a_closes_exit_euro_offset_bit(sample) if window == "A" else ""
    )
    a_closes_exit_euro_gap_bit = (
        format_window_a_closes_exit_euro_gap_bit(sample) if window == "A" else ""
    )
    a_closes_exit_euro_conc_bit = (
        format_window_a_closes_exit_euro_conc_bit(sample) if window == "A" else ""
    )
    a_closes_exit_euro_count_skew_bit = (
        format_window_a_closes_exit_euro_count_skew_bit(sample)
        if window == "A"
        else ""
    )
    a_closes_exit_euro_size_bit = (
        format_window_a_closes_exit_euro_size_bit(sample) if window == "A" else ""
    )
    a_closes_exit_euro_size_n_bit = (
        format_window_a_closes_exit_euro_size_n_bit(sample)
        if window == "A"
        else ""
    )
    a_closes_exit_euro_size_rest_n_bit = (
        format_window_a_closes_exit_euro_size_rest_n_bit(sample)
        if window == "A"
        else ""
    )
    a_closes_exit_euro_size_sign_bit = (
        format_window_a_closes_exit_euro_size_sign_bit(sample)
        if window == "A"
        else ""
    )
    a_closes_exit_euro_size_rest_sign_bit = (
        format_window_a_closes_exit_euro_size_rest_sign_bit(sample)
        if window == "A"
        else ""
    )
    a_closes_exit_euro_size_sign_clash_bit = (
        format_window_a_closes_exit_euro_size_sign_clash_bit(sample)
        if window == "A"
        else ""
    )
    a_closes_exit_euro_size_sign_clash_net_bit = (
        format_window_a_closes_exit_euro_size_sign_clash_net_bit(sample)
        if window == "A"
        else ""
    )
    a_closes_exit_euro_size_sign_clash_keep_bit = (
        format_window_a_closes_exit_euro_size_sign_clash_keep_bit(sample)
        if window == "A"
        else ""
    )
    a_closes_exit_euro_size_sign_clash_keep_fees_bit = (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_bit(sample)
        if window == "A"
        else ""
    )
    a_closes_exit_euro_size_sign_clash_keep_fees_vs_bit = (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_bit(sample)
        if window == "A"
        else ""
    )
    a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_bit = (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_bit(
            sample
        )
        if window == "A"
        else ""
    )
    a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_bit = (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_bit(
            sample
        )
        if window == "A"
        else ""
    )
    a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_bit = (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_bit(
            sample
        )
        if window == "A"
        else ""
    )
    a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_bit = (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_bit(
            sample
        )
        if window == "A"
        else ""
    )
    a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit = (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit(
            sample
        )
        if window == "A"
        else ""
    )
    a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_bit = (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_bit(
            sample
        )
        if window == "A"
        else ""
    )
    a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_bit = (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_bit(
            sample
        )
        if window == "A"
        else ""
    )
    a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_bit = (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_bit(
            sample
        )
        if window == "A"
        else ""
    )
    a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size_bit = (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size_bit(
            sample
        )
        if window == "A"
        else ""
    )
    a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_bit = (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_bit(
            sample
        )
        if window == "A"
        else ""
    )
    a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_bit = (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_bit(
            sample
        )
        if window == "A"
        else ""
    )
    a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_bit = (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_bit(
            sample
        )
        if window == "A"
        else ""
    )
    a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_bit = (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_bit(
            sample
        )
        if window == "A"
        else ""
    )
    a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_bit = (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_bit(
            sample
        )
        if window == "A"
        else ""
    )
    a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_bit = (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_bit(
            sample
        )
        if window == "A"
        else ""
    )
    a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_bit = (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_bit(
            sample
        )
        if window == "A"
        else ""
    )
    a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit = (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit(
            sample
        )
        if window == "A"
        else ""
    )
    a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size_bit = (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size_bit(
            sample
        )
        if window == "A"
        else ""
    )
    a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_bit = (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_bit(
            sample
        )
        if window == "A"
        else ""
    )
    a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_bit = (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_bit(
            sample
        )
        if window == "A"
        else ""
    )
    a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_bit = (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_bit(
            sample
        )
        if window == "A"
        else ""
    )
    a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_bit = (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_bit(
            sample
        )
        if window == "A"
        else ""
    )
    a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_bit = (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_bit(
            sample
        )
        if window == "A"
        else ""
    )
    a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta_bit = (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta_bit(
            sample
        )
        if window == "A"
        else ""
    )
    a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_bit = (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_bit(
            sample
        )
        if window == "A"
        else ""
    )
    a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit = (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit(
            sample
        )
        if window == "A"
        else ""
    )
    a_closes_exit_unknown_bit = (
        format_window_a_closes_exit_unknown_bit(sample) if window == "A" else ""
    )
    a_closes_flat_bit = (
        format_window_a_closes_flat_bit(sample) if window == "A" else ""
    )
    a_closes_payoff_bit = (
        format_window_a_closes_payoff_bit(sample) if window == "A" else ""
    )
    a_closes_expectancy_bit = (
        format_window_a_closes_expectancy_bit(sample) if window == "A" else ""
    )
    a_closes_net_expectancy_bit = (
        format_window_a_closes_net_expectancy_bit(sample)
        if window == "A"
        else ""
    )
    a_closes_fee_take_bit = (
        format_window_a_closes_fee_take_bit(sample) if window == "A" else ""
    )
    a_closes_net_vs_fee_bit = (
        format_window_a_closes_net_vs_fee_bit(sample) if window == "A" else ""
    )
    a_closes_net_profit_factor_bit = (
        format_window_a_closes_net_profit_factor_bit(sample)
        if window == "A"
        else ""
    )
    a_closes_profit_factor_bit = (
        format_window_a_closes_profit_factor_bit(sample) if window == "A" else ""
    )

    def _honesty_bits() -> list[str]:
        """Close-stat bits. The short line stays the decision; these fold under details."""
        return [
            b
            for b in (
                a_fee_status_bit,
                a_closes_polarity_bit,
                a_closes_win_rate_bit,
                a_closes_wr_vs_be_bit,
                a_closes_kelly_bit,
                a_closes_half_kelly_bit,
                a_closes_half_kelly_slot_bit,
                a_closes_half_kelly_cap_bit,
                a_closes_quarter_kelly_bit,
                a_closes_quarter_kelly_slot_bit,
                a_closes_quarter_kelly_cap_bit,
                a_closes_practical_kelly_bit,
                a_closes_kelly_sample_bit,
                a_closes_loss_streak_bit,
                a_closes_loss_streak_max_bit,
                a_closes_loss_streak_mean_bit,
                a_closes_loss_streak_median_bit,
                a_closes_loss_streak_min_bit,
                a_closes_loss_streak_stdev_bit,
                a_closes_loss_streak_cv_bit,
                a_closes_win_streak_bit,
                a_closes_win_streak_max_bit,
                a_closes_win_streak_mean_bit,
                a_closes_win_streak_median_bit,
                a_closes_win_streak_min_bit,
                a_closes_win_streak_stdev_bit,
                a_closes_win_streak_cv_bit,
                a_closes_exit_mix_bit,
                a_closes_exit_tp_share_bit,
                a_closes_exit_sl_share_bit,
                a_closes_exit_rot_share_bit,
                a_closes_exit_trim_share_bit,
                a_closes_exit_lead_bit,
                a_closes_exit_euro_lead_bit,
                a_closes_exit_euro_offset_bit,
                a_closes_exit_euro_gap_bit,
                a_closes_exit_euro_conc_bit,
                a_closes_exit_euro_count_skew_bit,
                a_closes_exit_euro_size_bit,
                a_closes_exit_euro_size_n_bit,
                a_closes_exit_euro_size_rest_n_bit,
                a_closes_exit_euro_size_sign_bit,
                a_closes_exit_euro_size_rest_sign_bit,
                a_closes_exit_euro_size_sign_clash_bit,
                a_closes_exit_euro_size_sign_clash_net_bit,
                a_closes_exit_euro_size_sign_clash_keep_bit,
                a_closes_exit_euro_size_sign_clash_keep_fees_bit,
                a_closes_exit_euro_size_sign_clash_keep_fees_vs_bit,
                a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_bit,
                a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_bit,
                a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_bit,
                a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_bit,
                a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit,
                a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_bit,
                a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_bit,
                a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_bit,
                a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size_bit,
                a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_bit,
                a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_bit,
                a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_bit,
                a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_bit,
                a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_bit,
                a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_bit,
                a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_bit,
                a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit,
                a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size_bit,
                a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_bit,
                a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_bit,
                a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_bit,
                a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_bit,
                a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_bit,
                a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta_bit,
                a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_bit,
                a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit,
                a_closes_exit_unknown_bit,
                a_closes_flat_bit,
                a_closes_payoff_bit,
                a_closes_expectancy_bit,
                a_closes_net_expectancy_bit,
                a_closes_fee_take_bit,
                a_closes_net_vs_fee_bit,
                a_closes_profit_factor_bit,
                a_closes_net_profit_factor_bit,
            )
            if b
        ]

    def _prefix_honesty(base: str) -> str:
        """Prepend close-stat bits so `line` stays one string for tests."""
        bits = _honesty_bits()
        if not bits:
            return base
        return " · ".join([*bits, base])

    def _honesty_warn() -> bool:
        """Warn on fee drag / fees thin / all-loss / loss-lean / WR·Kelly·payoff·PF thin / neg Kelly / half-Kelly under sizer·slot·cap / quarter-Kelly under sizer·slot·cap / practical Kelly cut·none / Kelly sample thin / loss streak hot / loss streak max hot / loss streak mean hot / loss streak med hot / loss streak min hot / loss streak σ hot / loss streak CV hot / exit mix hot / tp share thin / sl share hot / rot share hot / trim share hot / euro offset hot / euro gap hot / euro conc hot / euro count skew hot / euro size hot / euro size n thin / euro size rest n thin / euro size sign loss / euro size rest sign loss / euro size sign clash lead-loss / euro size clash net loss / euro size clash keep thin / clash keep fees eat·thin / unknown exits / neg·thin expectancy / net expect / fee take / net PF / WR below BE / thin WR edge."""
        return bool(
            a_fee_drag_bit
            or fees_thin
            or closes_all_loss
            or closes_loss_lean
            or closes_win_rate_thin
            or closes_wr_below_be
            or closes_wr_edge_thin
            or closes_kelly_neg
            or closes_kelly_thin
            or closes_half_kelly_under
            or closes_half_kelly_slot_under
            or closes_half_kelly_cap_under
            or closes_quarter_kelly_under
            or closes_quarter_kelly_slot_under
            or closes_quarter_kelly_cap_under
            or closes_practical_kelly_cut
            or closes_kelly_sample_thin
            or closes_loss_streak_hot
            or closes_loss_streak_max_hot
            or closes_loss_streak_mean_hot
            or closes_loss_streak_median_hot
            or closes_loss_streak_min_hot
            or closes_loss_streak_stdev_hot
            or closes_loss_streak_cv_hot
            or closes_flat_warn
            or closes_exit_mix_hot
            or closes_exit_tp_share_thin
            or closes_exit_sl_share_hot
            or closes_exit_rot_share_hot
            or closes_exit_trim_share_hot
            or closes_exit_lead_hot
            or closes_exit_euro_lead_hot
            or closes_exit_euro_offset_hot
            or closes_exit_euro_gap_hot
            or closes_exit_euro_conc_hot
            or closes_exit_euro_count_skew_hot
            or closes_exit_euro_size_hot
            or closes_exit_euro_size_n_thin
            or closes_exit_euro_size_rest_n_thin
            or closes_exit_euro_size_sign_loss
            or closes_exit_euro_size_rest_sign_loss
            or closes_exit_euro_size_sign_clash_loss
            or closes_exit_euro_size_sign_clash_net_loss
            or closes_exit_euro_size_sign_clash_keep_thin
            or closes_exit_euro_size_sign_clash_keep_fees_warn
            or closes_exit_euro_size_sign_clash_keep_fees_vs_warn
            or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_warn
            or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_warn
            or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_warn
            or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_warn
            or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_warn
            or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_warn
            or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_warn
            or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_warn
            or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size_warn
            or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_warn
            or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_warn
            or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_warn
            or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_warn
            or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_warn
            or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_warn
            or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_warn
            or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_warn
            or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size_warn
            or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_warn
            or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_warn
            or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_warn
            or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_warn
            or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_warn
            or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta_warn
            or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_warn
            or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_warn
            or closes_exit_unknown_warn
            or closes_payoff_thin
            or closes_expectancy_neg
            or closes_expectancy_thin
            or closes_net_expectancy_neg
            or closes_net_expectancy_thin
            or closes_net_expectancy_eats_edge
            or closes_fee_take_thin
            or closes_net_vs_fee_thin
            or closes_profit_factor_thin
            or closes_net_profit_factor_thin
            or closes_net_profit_factor_eats_edge
        )

    # Dual progress already shows N/M fills — omit trailing fill count from fees bit.
    stats_bit = format_window_stats_bit(
        stats, include_fills=not bool(a_fill_progress_bit)
    )
    # Window B start needs knobs + (for A) a non-thin fill sample with closes.
    b_ready = b_knobs_ready and (sample_ready if window == "A" and sample_known else True)
    if not protocol_ok:
        tone = "warn"
        if window == "A":
            status = "promote should be OFF for control"
        else:
            status = "promote should be ON for Window B"
    elif target_met:
        if window == "A" and a_thin_bit and sample_known:
            tone = "warn"
            status = f"{a_thin_bit} · keep Window A"
        elif window == "A" and a_open_only_bit and sample_known:
            tone = "warn"
            status = f"{a_open_only_bit} · keep Window A"
        elif window == "A" and a_thin_closes_bit and sample_known:
            tone = "warn"
            status = f"{a_thin_closes_bit} · keep Window A"
        elif window == "A" and a_stale_closes_bit and sample_known:
            tone = "warn"
            status = f"{a_stale_closes_bit} · keep Window A"
        elif window == "A" and b_block_bit:
            tone = "warn"
            status = b_block_bit
        elif window == "A" and a_aging_closes_bit and sample_known:
            # Aging warns but does not block ready for B (stale alone blocks).
            tone = "warn"
            base = (
                f"{a_aging_closes_bit} · ready for B"
                if stats_bit
                else f"{a_aging_closes_bit} · target met"
            )
            status = _prefix_honesty(base)
        elif window == "A" and a_fresh_closes_bit and sample_known:
            # Fresh completes RyanJHamby triad (was silent before).
            base = (
                f"{a_fresh_closes_bit} · ready for B"
                if stats_bit
                else f"{a_fresh_closes_bit} · target met"
            )
            status = _prefix_honesty(base)
            tone = "warn" if _honesty_warn() else "ready"
        else:
            if window == "A" and sample_known and sample_ready and (
                a_fee_status_bit
                or a_closes_polarity_bit
                or a_closes_win_rate_bit
                or a_closes_wr_vs_be_bit
                or a_closes_kelly_bit
                or a_closes_half_kelly_bit
                or a_closes_half_kelly_slot_bit
                or a_closes_half_kelly_cap_bit
                or a_closes_quarter_kelly_bit
                or a_closes_quarter_kelly_slot_bit
                or a_closes_quarter_kelly_cap_bit
                or a_closes_practical_kelly_bit
                or a_closes_kelly_sample_bit
                or a_closes_loss_streak_bit
                or a_closes_loss_streak_max_bit
                or a_closes_loss_streak_mean_bit
                or a_closes_loss_streak_median_bit
                or a_closes_loss_streak_min_bit
                or a_closes_loss_streak_stdev_bit
                or a_closes_loss_streak_cv_bit
                or a_closes_win_streak_bit
                or a_closes_win_streak_max_bit
                or a_closes_win_streak_mean_bit
                or a_closes_win_streak_median_bit
                or a_closes_win_streak_min_bit
                or a_closes_win_streak_stdev_bit
                or a_closes_win_streak_cv_bit
                or a_closes_exit_mix_bit
                or a_closes_exit_tp_share_bit
                or a_closes_exit_sl_share_bit
                or a_closes_exit_rot_share_bit
                or a_closes_exit_trim_share_bit
                or a_closes_exit_lead_bit
                or a_closes_exit_euro_lead_bit
                or a_closes_exit_euro_offset_bit
                or a_closes_exit_euro_gap_bit
                or a_closes_exit_euro_conc_bit
                or a_closes_exit_euro_count_skew_bit
                or a_closes_exit_euro_size_bit
                or a_closes_exit_euro_size_n_bit
                or a_closes_exit_euro_size_rest_n_bit
                or a_closes_exit_euro_size_sign_bit
                or a_closes_exit_euro_size_rest_sign_bit
                or a_closes_exit_euro_size_sign_clash_bit
                or a_closes_exit_euro_size_sign_clash_net_bit
                or a_closes_exit_euro_size_sign_clash_keep_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit
                or a_closes_exit_unknown_bit
                or a_closes_flat_bit
                or a_closes_payoff_bit
                or a_closes_expectancy_bit
                or a_closes_net_expectancy_bit
                or a_closes_fee_take_bit
                or a_closes_net_vs_fee_bit
                or a_closes_profit_factor_bit
                or a_closes_net_profit_factor_bit
            ):
                # Fee / polarity / WR / vs-BE / Kelly / half-Kelly / slot / cap / quarter / quarter-slot / quarter-cap / practical / payoff / expectancy / net / fee take / PF / net PF / loss max / loss σ warn; still ready for B.
                tone = "warn" if _honesty_warn() else "ready"
                status = _prefix_honesty(
                    "ready for B" if stats_bit else "target met"
                )
            else:
                tone = "ready"
                if window == "A":
                    status = (
                        "ready for B" if stats_bit else "target met · summarize before B"
                    )
                else:
                    status = "target met · write fee-adjusted verdict"
    else:
        tone = "progress"
        # Days still running: multi-meter honesty (fills · sells · open-only).
        if window == "A" and sample_known and a_thin_bit:
            status = "building sample"
        elif window == "A" and sample_known and a_open_only_bit:
            status = f"{a_open_only_bit} · keep Window A"
        elif window == "A" and sample_known and a_thin_closes_bit:
            # Fills ok but close floor short — parallel to building sample.
            status = "building closes"
        elif window == "A" and sample_known and a_stale_closes_bit:
            status = f"{a_stale_closes_bit} · keep Window A"
        elif window == "A" and sample_known and a_aging_closes_bit and sample_ready:
            tone = "warn"
            base = f"{a_aging_closes_bit} · sample ready · keep Window A"
            status = _prefix_honesty(base)
        elif window == "A" and sample_known and a_fresh_closes_bit and sample_ready:
            base = f"{a_fresh_closes_bit} · sample ready · keep Window A"
            status = _prefix_honesty(base)
            if _honesty_warn():
                tone = "warn"
        elif window == "A" and sample_known and sample_ready:
            if (
                a_fee_status_bit
                or a_closes_polarity_bit
                or a_closes_win_rate_bit
                or a_closes_wr_vs_be_bit
                or a_closes_kelly_bit
                or a_closes_half_kelly_bit
                or a_closes_half_kelly_slot_bit
                or a_closes_half_kelly_cap_bit
                or a_closes_quarter_kelly_bit
                or a_closes_quarter_kelly_slot_bit
                or a_closes_quarter_kelly_cap_bit
                or a_closes_practical_kelly_bit
                or a_closes_kelly_sample_bit
                or a_closes_loss_streak_bit
                or a_closes_loss_streak_max_bit
                or a_closes_loss_streak_mean_bit
                or a_closes_loss_streak_median_bit
                or a_closes_loss_streak_min_bit
                or a_closes_loss_streak_stdev_bit
                or a_closes_loss_streak_cv_bit
                or a_closes_win_streak_bit
                or a_closes_win_streak_max_bit
                or a_closes_win_streak_mean_bit
                or a_closes_win_streak_median_bit
                or a_closes_win_streak_min_bit
                or a_closes_win_streak_stdev_bit
                or a_closes_win_streak_cv_bit
                or a_closes_exit_mix_bit
                or a_closes_exit_tp_share_bit
                or a_closes_exit_sl_share_bit
                or a_closes_exit_rot_share_bit
                or a_closes_exit_trim_share_bit
                or a_closes_exit_lead_bit
                or a_closes_exit_euro_lead_bit
                or a_closes_exit_euro_offset_bit
                or a_closes_exit_euro_gap_bit
                or a_closes_exit_euro_conc_bit
                or a_closes_exit_euro_count_skew_bit
                or a_closes_exit_euro_size_bit
                or a_closes_exit_euro_size_n_bit
                or a_closes_exit_euro_size_rest_n_bit
                or a_closes_exit_euro_size_sign_bit
                or a_closes_exit_euro_size_rest_sign_bit
                or a_closes_exit_euro_size_sign_clash_bit
                or a_closes_exit_euro_size_sign_clash_net_bit
                or a_closes_exit_euro_size_sign_clash_keep_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_bit
                or a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit
                or a_closes_exit_unknown_bit
                or a_closes_flat_bit
                or a_closes_payoff_bit
                or a_closes_expectancy_bit
                or a_closes_net_expectancy_bit
                or a_closes_fee_take_bit
                or a_closes_net_vs_fee_bit
                or a_closes_profit_factor_bit
                or a_closes_net_profit_factor_bit
            ):
                if _honesty_warn():
                    tone = "warn"
                status = _prefix_honesty("sample ready · keep Window A")
            else:
                status = "sample ready · keep Window A"
        else:
            status = "running"
    honesty_bits = _honesty_bits()
    honesty_line = ""
    honesty_core = ""
    fees_line = ""
    polarity_line = ""
    kelly_line = ""
    streak_line = ""
    exit_mix_line = ""
    exit_euro_line = ""
    fee_pressure_line = ""
    align_nest_line = ""
    align_deep_line = ""
    edge_line = ""
    honesty_warns: list[str] = []
    summary_status = status
    if honesty_bits:
        joined = " · ".join(honesty_bits)
        prefix = f"{joined} · "
        if status.startswith(prefix):
            honesty_line = joined
            summary_status = status[len(prefix) :]
            # Rare ladders stay out of the main close paragraph
            # (MonsterDeveloper fold). `honesty_line` stays the full string.
            fee_pressure_all = [b for b in honesty_bits if "clash keep fees" in b]
            # Nested align cascade after first share vs Δ align (MonsterDeveloper
            # declutter + xang1234 severity). First align stays on fee pressure.
            # Deep = second cascade after nested share vs Δ align (Level C+).
            _ALIGN_DEEP_MARK = (
                "align lead size sides share vs Δ align size",
                "align lead size sides share vs Δ align lead",
            )
            align_cascade_bits = [
                b
                for b in fee_pressure_all
                if "share vs Δ align size" in b or "share vs Δ align lead" in b
            ]
            align_deep_bits = [
                b
                for b in align_cascade_bits
                if any(m in b for m in _ALIGN_DEEP_MARK)
            ]
            align_nest_bits = [
                b for b in align_cascade_bits if b not in align_deep_bits
            ]
            fee_pressure_bits = [
                b for b in fee_pressure_all if b not in align_cascade_bits
            ]
            exit_euro_bits = [
                b
                for b in honesty_bits
                if b.startswith("A exits €") and b not in fee_pressure_all
            ]
            # Count mix · shares · unknown (not € lead / clash).
            exit_mix_bits = [
                b
                for b in honesty_bits
                if b.startswith("A exits") and not b.startswith("A exits €")
            ]
            kelly_bits = [b for b in honesty_bits if "Kelly" in b]
            streak_bits = [
                b
                for b in honesty_bits
                if "streak" in b or b.startswith("A flats")
            ]
            # Payoff · expectancy · PF · win rate. Not fee drag, polarity, or exit counts.
            edge_prefixes = (
                "A payoff",
                "A expectancy",
                "A PF",
                "A win rate",
                "A WR ",
                "A net expect",
                "A fee take",
                "A net/fee",
                "A net PF",
            )
            edge_bits = [
                b for b in honesty_bits if b.startswith(edge_prefixes)
            ]
            # Fee drag / fees-ok. Not fee take (that stays on the edge fold).
            fees_bits = [
                b
                for b in honesty_bits
                if b.startswith(("A fee drag", "A fees "))
            ]
            polarity_bits = [
                b
                for b in honesty_bits
                if b.startswith(("A all-win", "A all-loss", "A mixed"))
            ]
            folded = {
                *fee_pressure_bits,
                *align_nest_bits,
                *align_deep_bits,
                *exit_euro_bits,
                *exit_mix_bits,
                *kelly_bits,
                *streak_bits,
                *edge_bits,
                *fees_bits,
                *polarity_bits,
            }
            core_bits = [b for b in honesty_bits if b not in folded]
            honesty_core = " · ".join(core_bits)
            fees_line = " · ".join(fees_bits)
            polarity_line = " · ".join(polarity_bits)
            kelly_line = " · ".join(kelly_bits)
            streak_line = " · ".join(streak_bits)
            exit_mix_line = " · ".join(exit_mix_bits)
            exit_euro_line = " · ".join(exit_euro_bits)
            fee_pressure_line = " · ".join(fee_pressure_bits)
            align_nest_line = " · ".join(align_nest_bits)
            align_deep_line = " · ".join(align_deep_bits)
            edge_line = " · ".join(edge_bits)
            # Name hot folds on the summary (xang1234 severity). Quiet stays quiet.
            if fees_line and (a_fee_drag_bit or fees_thin):
                honesty_warns.append("fees")
            if polarity_line and (closes_all_loss or closes_loss_lean):
                honesty_warns.append("polarity")
            if edge_line and (
                closes_win_rate_thin
                or closes_wr_below_be
                or closes_wr_edge_thin
                or closes_payoff_thin
                or closes_expectancy_neg
                or closes_expectancy_thin
                or closes_net_expectancy_neg
                or closes_net_expectancy_thin
                or closes_net_expectancy_eats_edge
                or closes_fee_take_thin
                or closes_net_vs_fee_thin
                or closes_profit_factor_thin
                or closes_net_profit_factor_thin
                or closes_net_profit_factor_eats_edge
            ):
                honesty_warns.append("edge")
            if kelly_line and (
                closes_kelly_neg
                or closes_kelly_thin
                or closes_half_kelly_under
                or closes_half_kelly_slot_under
                or closes_half_kelly_cap_under
                or closes_quarter_kelly_under
                or closes_quarter_kelly_slot_under
                or closes_quarter_kelly_cap_under
                or closes_practical_kelly_cut
                or closes_kelly_sample_thin
            ):
                honesty_warns.append("Kelly")
            if streak_line and (
                closes_loss_streak_hot
                or closes_loss_streak_max_hot
                or closes_loss_streak_mean_hot
                or closes_loss_streak_median_hot
                or closes_loss_streak_min_hot
                or closes_loss_streak_stdev_hot
                or closes_loss_streak_cv_hot
                or closes_flat_warn
            ):
                honesty_warns.append("streaks")
            if exit_mix_line and (
                closes_exit_mix_hot
                or closes_exit_tp_share_thin
                or closes_exit_sl_share_hot
                or closes_exit_rot_share_hot
                or closes_exit_trim_share_hot
                or closes_exit_lead_hot
                or closes_exit_unknown_warn
            ):
                honesty_warns.append("exit mix")
            if exit_euro_line and (
                closes_exit_euro_lead_hot
                or closes_exit_euro_offset_hot
                or closes_exit_euro_gap_hot
                or closes_exit_euro_conc_hot
                or closes_exit_euro_count_skew_hot
                or closes_exit_euro_size_hot
                or closes_exit_euro_size_n_thin
                or closes_exit_euro_size_rest_n_thin
                or closes_exit_euro_size_sign_loss
                or closes_exit_euro_size_rest_sign_loss
                or closes_exit_euro_size_sign_clash_loss
                or closes_exit_euro_size_sign_clash_net_loss
                or closes_exit_euro_size_sign_clash_keep_thin
            ):
                honesty_warns.append("exit euros")
            if fee_pressure_line and (
                closes_exit_euro_size_sign_clash_keep_fees_warn
                or closes_exit_euro_size_sign_clash_keep_fees_vs_warn
                or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_warn
                or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_warn
                or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_warn
                or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_warn
                or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_warn
                or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_warn
                or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_warn
                or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_warn
            ):
                honesty_warns.append("fee pressure")
            if align_nest_line and (
                closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size_warn
                or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_warn
                or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_warn
                or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_warn
                or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_warn
                or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_warn
                or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_warn
                or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_warn
                or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_warn
            ):
                honesty_warns.append("align nest")
            if align_deep_line and (
                closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size_warn
                or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_warn
                or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_warn
                or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_warn
                or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_warn
                or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_warn
                or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta_warn
                or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_warn
                or closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_warn
            ):
                honesty_warns.append("align deep")
    # Populated child-fold labels (same order as folds). Quiet summary names them.
    honesty_folds = [
        label
        for label, line in (
            ("fees", fees_line),
            ("polarity", polarity_line),
            ("edge", edge_line),
            ("Kelly", kelly_line),
            ("streaks", streak_line),
            ("exit mix", exit_mix_line),
            ("exit euros", exit_euro_line),
            ("fee pressure", fee_pressure_line),
            ("align nest", align_nest_line),
            ("align deep", align_deep_line),
        )
        if (line or "").strip()
    ]
    # Calm folds when hot (portfolio AI speak-both-sides): warn names heat;
    # quiet names the rest + count so friends need not open every cold fold
    # (tradermonty preserve diagnostics).
    warn_set = set(honesty_warns)
    honesty_quiet_folds = [label for label in honesty_folds if label not in warn_set]
    parts = [
        f"Window {window}",
        f"promote {promote_label}",
        f"{days}/{need} days",
    ]
    if a_fill_progress_bit:
        parts.append(a_fill_progress_bit)
    if stats_bit and protocol_ok:
        parts.append(stats_bit)
    parts.append(status)
    line = " · ".join(parts)
    summary_line = " · ".join([*parts[:-1], summary_status])
    # Allow room for N/M sells + fee / polarity / WR / vs-BE / Kelly / half-Kelly / slot / cap / quarter / practical / Kelly sample / loss streak / loss max / loss mean / loss med / loss min / loss σ / win streak / win max / win mean / win med / win min / flats / payoff / expectancy / net / fee take / PF / net PF / freshness.
    if len(line) > 1260:
        line = line[:1149] + "…"
    return {
        "ready": True,
        "tone": tone,
        "line": line,
        "summary_line": summary_line,
        "honesty_line": honesty_line,
        "honesty_core": honesty_core,
        "fees_line": fees_line,
        "polarity_line": polarity_line,
        "kelly_line": kelly_line,
        "streak_line": streak_line,
        "exit_mix_line": exit_mix_line,
        "exit_euro_line": exit_euro_line,
        "fee_pressure_line": fee_pressure_line,
        "align_nest_line": align_nest_line,
        "align_deep_line": align_deep_line,
        "edge_line": edge_line,
        "honesty_warns": honesty_warns,
        # Count first so friends see how hot Close honesty is without scanning
        # every fold name (MonsterDeveloper declutter + xang1234 severity).
        "honesty_warn_count": len(honesty_warns),
        # Child-fold inventory (portfolio AI speak-both-sides + xang1234):
        # quiet · N folds · fees · … /
        # warn · N hot of M · fees · … · quiet · K folds · edge · ….
        # honesty_core is not a fold. Quiet names populated folds; hot also
        # names calm folds + calm count (tradermonty preserve diagnostics).
        "honesty_folds": honesty_folds,
        "honesty_fold_count": len(honesty_folds),
        "honesty_quiet_folds": honesty_quiet_folds,
        "honesty_quiet_fold_count": len(honesty_quiet_folds),
        "window": window,
        "trading_days": days,
        "target_days": need,
        "target_met": target_met,
        "protocol_ok": protocol_ok,
        "promote_on": promote_on,
        "window_stats": stats,
        "window_stats_bit": stats_bit,
        "sample_ready": sample_ready if window == "A" else True,
        "sample_known": sample_known if window == "A" else False,
        "sample_fills": sample_fills if window == "A" else 0,
        "target_fills": target_fills if window == "A" else 0,
        "sample_buys": sample_buys if window == "A" else 0,
        "sample_sells": sample_sells if window == "A" else 0,
        "sample_open_only": sample_open_only if window == "A" else False,
        "sample_thin_closes": sample_thin_closes if window == "A" else False,
        "sample_stale_closes": sample_stale_closes if window == "A" else False,
        "sample_aging_closes": sample_aging_closes if window == "A" else False,
        "sample_fresh_closes": sample_fresh_closes if window == "A" else False,
        "closes_freshness": closes_freshness if window == "A" else "",
        "sample_fee_drag": sample_fee_drag if window == "A" else False,
        "fee_drag_severity": fee_drag_severity if window == "A" else "",
        "sample_fees_ok": sample_fees_ok if window == "A" else False,
        "fees_ok_severity": fees_ok_severity if window == "A" else "",
        "closes_polarity": closes_polarity if window == "A" else "",
        "closes_polarity_lean": closes_polarity_lean if window == "A" else "",
        "closes_all_loss": closes_all_loss if window == "A" else False,
        "closes_loss_lean": closes_loss_lean if window == "A" else False,
        "closes_payoff_ratio": closes_payoff_ratio if window == "A" else None,
        "closes_payoff_severity": closes_payoff_severity if window == "A" else "",
        "closes_payoff_thin": closes_payoff_thin if window == "A" else False,
        "closes_expectancy": closes_expectancy if window == "A" else None,
        "closes_expectancy_neg": closes_expectancy_neg if window == "A" else False,
        "closes_expectancy_severity": (
            closes_expectancy_severity if window == "A" else ""
        ),
        "closes_expectancy_thin": closes_expectancy_thin if window == "A" else False,
        "closes_expectancy_ratio": (
            closes_expectancy_ratio if window == "A" else None
        ),
        "closes_profit_factor": closes_profit_factor if window == "A" else None,
        "closes_profit_factor_severity": (
            closes_profit_factor_severity if window == "A" else ""
        ),
        "closes_profit_factor_thin": (
            closes_profit_factor_thin if window == "A" else False
        ),
        "closes_win_rate_pct": closes_win_rate_pct if window == "A" else None,
        "closes_win_rate_severity": (
            closes_win_rate_severity if window == "A" else ""
        ),
        "closes_win_rate_thin": closes_win_rate_thin if window == "A" else False,
        "closes_breakeven_wr_pct": (
            closes_breakeven_wr_pct if window == "A" else None
        ),
        "closes_wr_vs_be": closes_wr_vs_be if window == "A" else "",
        "closes_wr_below_be": closes_wr_below_be if window == "A" else False,
        "closes_wr_edge_pp": closes_wr_edge_pp if window == "A" else None,
        "closes_wr_edge_severity": (
            closes_wr_edge_severity if window == "A" else ""
        ),
        "closes_wr_edge_thin": closes_wr_edge_thin if window == "A" else False,
        "closes_kelly_pct": closes_kelly_pct if window == "A" else None,
        "closes_kelly_severity": closes_kelly_severity if window == "A" else "",
        "closes_kelly_thin": closes_kelly_thin if window == "A" else False,
        "closes_kelly_neg": closes_kelly_neg if window == "A" else False,
        "closes_half_kelly_pct": closes_half_kelly_pct if window == "A" else None,
        "closes_half_kelly_sizer_pct": (
            closes_half_kelly_sizer_pct if window == "A" else None
        ),
        "closes_half_kelly_vs": closes_half_kelly_vs if window == "A" else "",
        "closes_half_kelly_under": (
            closes_half_kelly_under if window == "A" else False
        ),
        "closes_half_kelly_slot_pct": (
            closes_half_kelly_slot_pct if window == "A" else None
        ),
        "closes_half_kelly_vs_slot": (
            closes_half_kelly_vs_slot if window == "A" else ""
        ),
        "closes_half_kelly_slot_under": (
            closes_half_kelly_slot_under if window == "A" else False
        ),
        "closes_half_kelly_cap_pct": (
            closes_half_kelly_cap_pct if window == "A" else None
        ),
        "closes_half_kelly_vs_cap": (
            closes_half_kelly_vs_cap if window == "A" else ""
        ),
        "closes_half_kelly_cap_under": (
            closes_half_kelly_cap_under if window == "A" else False
        ),
        "closes_quarter_kelly_pct": (
            closes_quarter_kelly_pct if window == "A" else None
        ),
        "closes_quarter_kelly_sizer_pct": (
            closes_quarter_kelly_sizer_pct if window == "A" else None
        ),
        "closes_quarter_kelly_vs": closes_quarter_kelly_vs if window == "A" else "",
        "closes_quarter_kelly_under": (
            closes_quarter_kelly_under if window == "A" else False
        ),
        "closes_quarter_kelly_slot_pct": (
            closes_quarter_kelly_slot_pct if window == "A" else None
        ),
        "closes_quarter_kelly_vs_slot": (
            closes_quarter_kelly_vs_slot if window == "A" else ""
        ),
        "closes_quarter_kelly_slot_under": (
            closes_quarter_kelly_slot_under if window == "A" else False
        ),
        "closes_quarter_kelly_cap_pct": (
            closes_quarter_kelly_cap_pct if window == "A" else None
        ),
        "closes_quarter_kelly_vs_cap": (
            closes_quarter_kelly_vs_cap if window == "A" else ""
        ),
        "closes_quarter_kelly_cap_under": (
            closes_quarter_kelly_cap_under if window == "A" else False
        ),
        "closes_practical_kelly": (
            closes_practical_kelly if window == "A" else ""
        ),
        "closes_practical_kelly_pct": (
            closes_practical_kelly_pct if window == "A" else None
        ),
        "closes_practical_kelly_cut": (
            closes_practical_kelly_cut if window == "A" else False
        ),
        "closes_kelly_sample": closes_kelly_sample if window == "A" else "",
        "closes_kelly_sample_n": (
            closes_kelly_sample_n if window == "A" else None
        ),
        "closes_kelly_sample_thin": (
            closes_kelly_sample_thin if window == "A" else False
        ),
        "closes_loss_streak": closes_loss_streak if window == "A" else None,
        "closes_loss_streak_hot": (
            closes_loss_streak_hot if window == "A" else False
        ),
        "closes_loss_streak_max": (
            closes_loss_streak_max if window == "A" else None
        ),
        "closes_loss_streak_max_hot": (
            closes_loss_streak_max_hot if window == "A" else False
        ),
        "closes_loss_streak_mean": (
            closes_loss_streak_mean if window == "A" else None
        ),
        "closes_loss_streak_runs": (
            closes_loss_streak_runs if window == "A" else None
        ),
        "closes_loss_streak_mean_hot": (
            closes_loss_streak_mean_hot if window == "A" else False
        ),
        "closes_loss_streak_median": (
            closes_loss_streak_median if window == "A" else None
        ),
        "closes_loss_streak_median_hot": (
            closes_loss_streak_median_hot if window == "A" else False
        ),
        "closes_loss_streak_min": (
            closes_loss_streak_min if window == "A" else None
        ),
        "closes_loss_streak_min_hot": (
            closes_loss_streak_min_hot if window == "A" else False
        ),
        "closes_loss_streak_stdev": (
            closes_loss_streak_stdev if window == "A" else None
        ),
        "closes_loss_streak_stdev_hot": (
            closes_loss_streak_stdev_hot if window == "A" else False
        ),
        "closes_loss_streak_cv": (
            closes_loss_streak_cv if window == "A" else None
        ),
        "closes_loss_streak_cv_hot": (
            closes_loss_streak_cv_hot if window == "A" else False
        ),
        "closes_win_streak": closes_win_streak if window == "A" else None,
        "closes_win_streak_hot": (
            closes_win_streak_hot if window == "A" else False
        ),
        "closes_win_streak_max": closes_win_streak_max if window == "A" else None,
        "closes_win_streak_max_hot": (
            closes_win_streak_max_hot if window == "A" else False
        ),
        "closes_win_streak_mean": (
            closes_win_streak_mean if window == "A" else None
        ),
        "closes_win_streak_runs": (
            closes_win_streak_runs if window == "A" else None
        ),
        "closes_win_streak_mean_hot": (
            closes_win_streak_mean_hot if window == "A" else False
        ),
        "closes_win_streak_median": (
            closes_win_streak_median if window == "A" else None
        ),
        "closes_win_streak_median_hot": (
            closes_win_streak_median_hot if window == "A" else False
        ),
        "closes_win_streak_min": (
            closes_win_streak_min if window == "A" else None
        ),
        "closes_win_streak_min_hot": (
            closes_win_streak_min_hot if window == "A" else False
        ),
        "closes_win_streak_stdev": (
            closes_win_streak_stdev if window == "A" else None
        ),
        "closes_win_streak_stdev_hot": (
            closes_win_streak_stdev_hot if window == "A" else False
        ),
        "closes_win_streak_cv": (
            closes_win_streak_cv if window == "A" else None
        ),
        "closes_win_streak_cv_hot": (
            closes_win_streak_cv_hot if window == "A" else False
        ),
        "closes_flat": closes_flat if window == "A" else None,
        "closes_flat_warn": closes_flat_warn if window == "A" else False,
        "closes_exit_tp": closes_exit_tp if window == "A" else None,
        "closes_exit_sl": closes_exit_sl if window == "A" else None,
        "closes_exit_rot": closes_exit_rot if window == "A" else None,
        "closes_exit_trim": closes_exit_trim if window == "A" else None,
        "closes_exit_mix_hot": closes_exit_mix_hot if window == "A" else False,
        "closes_exit_unknown": closes_exit_unknown if window == "A" else None,
        "closes_exit_unknown_warn": (
            closes_exit_unknown_warn if window == "A" else False
        ),
        "closes_exit_tp_share_pct": (
            closes_exit_tp_share_pct if window == "A" else None
        ),
        "closes_exit_tp_share_severity": (
            closes_exit_tp_share_severity if window == "A" else ""
        ),
        "closes_exit_tp_share_thin": (
            closes_exit_tp_share_thin if window == "A" else False
        ),
        "closes_exit_sl_share_pct": (
            closes_exit_sl_share_pct if window == "A" else None
        ),
        "closes_exit_sl_share_severity": (
            closes_exit_sl_share_severity if window == "A" else ""
        ),
        "closes_exit_sl_share_hot": (
            closes_exit_sl_share_hot if window == "A" else False
        ),
        "closes_exit_rot_share_pct": (
            closes_exit_rot_share_pct if window == "A" else None
        ),
        "closes_exit_rot_share_severity": (
            closes_exit_rot_share_severity if window == "A" else ""
        ),
        "closes_exit_rot_share_hot": (
            closes_exit_rot_share_hot if window == "A" else False
        ),
        "closes_exit_trim_share_pct": (
            closes_exit_trim_share_pct if window == "A" else None
        ),
        "closes_exit_trim_share_severity": (
            closes_exit_trim_share_severity if window == "A" else ""
        ),
        "closes_exit_trim_share_hot": (
            closes_exit_trim_share_hot if window == "A" else False
        ),
        "closes_exit_lead": closes_exit_lead if window == "A" else None,
        "closes_exit_lead_pct": (
            closes_exit_lead_pct if window == "A" else None
        ),
        "closes_exit_lead_hot": (
            closes_exit_lead_hot if window == "A" else False
        ),
        "closes_exit_euro_lead": (
            closes_exit_euro_lead if window == "A" else None
        ),
        "closes_exit_euro_pnl": (
            closes_exit_euro_pnl if window == "A" else None
        ),
        "closes_exit_euro_lead_hot": (
            closes_exit_euro_lead_hot if window == "A" else False
        ),
        "closes_exit_euro_offset": (
            closes_exit_euro_offset if window == "A" else None
        ),
        "closes_exit_euro_offset_pnl": (
            closes_exit_euro_offset_pnl if window == "A" else None
        ),
        "closes_exit_euro_offset_ratio": (
            closes_exit_euro_offset_ratio if window == "A" else None
        ),
        "closes_exit_euro_offset_hot": (
            closes_exit_euro_offset_hot if window == "A" else False
        ),
        "closes_exit_euro_gap_ratio": (
            closes_exit_euro_gap_ratio if window == "A" else None
        ),
        "closes_exit_euro_gap_vs": (
            closes_exit_euro_gap_vs if window == "A" else None
        ),
        "closes_exit_euro_gap_hot": (
            closes_exit_euro_gap_hot if window == "A" else False
        ),
        "closes_exit_euro_conc": (
            closes_exit_euro_conc if window == "A" else None
        ),
        "closes_exit_euro_conc_pct": (
            closes_exit_euro_conc_pct if window == "A" else None
        ),
        "closes_exit_euro_conc_hot": (
            closes_exit_euro_conc_hot if window == "A" else False
        ),
        "closes_exit_euro_count_skew_pp": (
            closes_exit_euro_count_skew_pp if window == "A" else None
        ),
        "closes_exit_euro_count_skew_hot": (
            closes_exit_euro_count_skew_hot if window == "A" else False
        ),
        "closes_exit_euro_size_ratio": (
            closes_exit_euro_size_ratio if window == "A" else None
        ),
        "closes_exit_euro_size_hot": (
            closes_exit_euro_size_hot if window == "A" else False
        ),
        "closes_exit_euro_size_n": (
            closes_exit_euro_size_n if window == "A" else ""
        ),
        "closes_exit_euro_size_n_count": (
            closes_exit_euro_size_n_count if window == "A" else None
        ),
        "closes_exit_euro_size_n_thin": (
            closes_exit_euro_size_n_thin if window == "A" else False
        ),
        "closes_exit_euro_size_rest_n": (
            closes_exit_euro_size_rest_n if window == "A" else ""
        ),
        "closes_exit_euro_size_rest_n_count": (
            closes_exit_euro_size_rest_n_count if window == "A" else None
        ),
        "closes_exit_euro_size_rest_n_thin": (
            closes_exit_euro_size_rest_n_thin if window == "A" else False
        ),
        "closes_exit_euro_size_sign": (
            closes_exit_euro_size_sign if window == "A" else ""
        ),
        "closes_exit_euro_size_sign_pnl": (
            closes_exit_euro_size_sign_pnl if window == "A" else None
        ),
        "closes_exit_euro_size_sign_loss": (
            closes_exit_euro_size_sign_loss if window == "A" else False
        ),
        "closes_exit_euro_size_rest_sign": (
            closes_exit_euro_size_rest_sign if window == "A" else ""
        ),
        "closes_exit_euro_size_rest_sign_pnl": (
            closes_exit_euro_size_rest_sign_pnl if window == "A" else None
        ),
        "closes_exit_euro_size_rest_sign_loss": (
            closes_exit_euro_size_rest_sign_loss if window == "A" else False
        ),
        "closes_exit_euro_size_sign_clash": (
            closes_exit_euro_size_sign_clash if window == "A" else ""
        ),
        "closes_exit_euro_size_sign_clash_loss": (
            closes_exit_euro_size_sign_clash_loss if window == "A" else False
        ),
        "closes_exit_euro_size_sign_clash_net": (
            closes_exit_euro_size_sign_clash_net if window == "A" else ""
        ),
        "closes_exit_euro_size_sign_clash_net_pnl": (
            closes_exit_euro_size_sign_clash_net_pnl if window == "A" else None
        ),
        "closes_exit_euro_size_sign_clash_net_loss": (
            closes_exit_euro_size_sign_clash_net_loss if window == "A" else False
        ),
        "closes_exit_euro_size_sign_clash_keep": (
            closes_exit_euro_size_sign_clash_keep if window == "A" else ""
        ),
        "closes_exit_euro_size_sign_clash_keep_ratio": (
            closes_exit_euro_size_sign_clash_keep_ratio if window == "A" else None
        ),
        "closes_exit_euro_size_sign_clash_keep_thin": (
            closes_exit_euro_size_sign_clash_keep_thin if window == "A" else False
        ),
        "closes_exit_euro_size_sign_clash_keep_fees": (
            closes_exit_euro_size_sign_clash_keep_fees if window == "A" else ""
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_ratio": (
            closes_exit_euro_size_sign_clash_keep_fees_ratio
            if window == "A"
            else None
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_warn
            if window == "A"
            else False
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs": (
            closes_exit_euro_size_sign_clash_keep_fees_vs if window == "A" else ""
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_window": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_window
            if window == "A"
            else ""
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_warn
            if window == "A"
            else False
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap
            if window == "A"
            else ""
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_ratio": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_ratio
            if window == "A"
            else None
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_warn
            if window == "A"
            else False
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir
            if window == "A"
            else ""
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_ratio": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_ratio
            if window == "A"
            else None
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_warn
            if window == "A"
            else False
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_leftover": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_leftover
            if window == "A"
            else None
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_window": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_window
            if window == "A"
            else None
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_warn
            if window == "A"
            else False
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta
            if window == "A"
            else ""
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_ratio": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_ratio
            if window == "A"
            else None
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_warn
            if window == "A"
            else False
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_leftover": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_leftover
            if window == "A"
            else None
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_window": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_window
            if window == "A"
            else None
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_warn
            if window == "A"
            else False
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta
            if window == "A"
            else ""
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_ratio": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_ratio
            if window == "A"
            else None
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_warn
            if window == "A"
            else False
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta
            if window == "A"
            else ""
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_warn
            if window == "A"
            else False
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align
            if window == "A"
            else ""
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_warn
            if window == "A"
            else False
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size
            if window == "A"
            else ""
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size_warn
            if window == "A"
            else False
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead
            if window == "A"
            else ""
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_warn
            if window == "A"
            else False
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size
            if window == "A"
            else ""
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_warn
            if window == "A"
            else False
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_louder": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_louder
            if window == "A"
            else None
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_quieter": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_quieter
            if window == "A"
            else None
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_warn
            if window == "A"
            else False
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta
            if window == "A"
            else ""
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_ratio": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_ratio
            if window == "A"
            else None
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_warn
            if window == "A"
            else False
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_louder_pct": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_louder_pct
            if window == "A"
            else None
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_quieter_pct": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_quieter_pct
            if window == "A"
            else None
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_warn
            if window == "A"
            else False
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta
            if window == "A"
            else ""
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_ratio": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_ratio
            if window == "A"
            else None
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_warn
            if window == "A"
            else False
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta
            if window == "A"
            else ""
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_warn
            if window == "A"
            else False
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align
            if window == "A"
            else ""
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_warn
            if window == "A"
            else False
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size
            if window == "A"
            else ""
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size_warn
            if window == "A"
            else False
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead
            if window == "A"
            else ""
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_warn
            if window == "A"
            else False
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size
            if window == "A"
            else ""
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_warn
            if window == "A"
            else False
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_warn
            if window == "A"
            else False
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_warn
            if window == "A"
            else False
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_warn
            if window == "A"
            else False
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta_warn
            if window == "A"
            else False
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta if window == "A" else ""
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_warn
            if window == "A"
            else False
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align if window == "A" else ""
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_warn
            if window == "A"
            else False
        ),
        "closes_net_expectancy": closes_net_expectancy if window == "A" else None,
        "closes_net_expectancy_neg": (
            closes_net_expectancy_neg if window == "A" else False
        ),
        "closes_net_expectancy_severity": (
            closes_net_expectancy_severity if window == "A" else ""
        ),
        "closes_net_expectancy_thin": (
            closes_net_expectancy_thin if window == "A" else False
        ),
        "closes_net_expectancy_ratio": (
            closes_net_expectancy_ratio if window == "A" else None
        ),
        "closes_net_expectancy_eats_edge": (
            closes_net_expectancy_eats_edge if window == "A" else False
        ),
        "closes_fee_take": closes_fee_take if window == "A" else None,
        "closes_fee_take_severity": (
            closes_fee_take_severity if window == "A" else ""
        ),
        "closes_fee_take_thin": closes_fee_take_thin if window == "A" else False,
        "closes_fee_take_ratio": (
            closes_fee_take_ratio if window == "A" else None
        ),
        "closes_net_vs_fee": closes_net_vs_fee if window == "A" else None,
        "closes_net_vs_fee_severity": (
            closes_net_vs_fee_severity if window == "A" else ""
        ),
        "closes_net_vs_fee_thin": closes_net_vs_fee_thin if window == "A" else False,
        "closes_net_profit_factor": (
            closes_net_profit_factor if window == "A" else None
        ),
        "closes_net_profit_factor_severity": (
            closes_net_profit_factor_severity if window == "A" else ""
        ),
        "closes_net_profit_factor_thin": (
            closes_net_profit_factor_thin if window == "A" else False
        ),
        "closes_net_profit_factor_eats_edge": (
            closes_net_profit_factor_eats_edge if window == "A" else False
        ),
        "a_fill_progress_bit": a_fill_progress_bit,
        "a_thin_bit": a_thin_bit,
        "a_open_only_bit": a_open_only_bit,
        "a_thin_closes_bit": a_thin_closes_bit,
        "a_stale_closes_bit": a_stale_closes_bit,
        "a_aging_closes_bit": a_aging_closes_bit,
        "a_fresh_closes_bit": a_fresh_closes_bit,
        "a_fee_drag_bit": a_fee_drag_bit,
        "a_fees_ok_bit": a_fees_ok_bit,
        "a_closes_polarity_bit": a_closes_polarity_bit,
        "a_closes_win_rate_bit": a_closes_win_rate_bit,
        "a_closes_wr_vs_be_bit": a_closes_wr_vs_be_bit,
        "a_closes_kelly_bit": a_closes_kelly_bit,
        "a_closes_half_kelly_bit": a_closes_half_kelly_bit,
        "a_closes_half_kelly_slot_bit": a_closes_half_kelly_slot_bit,
        "a_closes_half_kelly_cap_bit": a_closes_half_kelly_cap_bit,
        "a_closes_quarter_kelly_bit": a_closes_quarter_kelly_bit,
        "a_closes_quarter_kelly_slot_bit": a_closes_quarter_kelly_slot_bit,
        "a_closes_quarter_kelly_cap_bit": a_closes_quarter_kelly_cap_bit,
        "a_closes_practical_kelly_bit": a_closes_practical_kelly_bit,
        "a_closes_kelly_sample_bit": a_closes_kelly_sample_bit,
        "a_closes_loss_streak_bit": a_closes_loss_streak_bit,
        "a_closes_loss_streak_max_bit": a_closes_loss_streak_max_bit,
        "a_closes_loss_streak_mean_bit": a_closes_loss_streak_mean_bit,
        "a_closes_loss_streak_median_bit": a_closes_loss_streak_median_bit,
        "a_closes_loss_streak_min_bit": a_closes_loss_streak_min_bit,
        "a_closes_loss_streak_stdev_bit": a_closes_loss_streak_stdev_bit,
        "a_closes_loss_streak_cv_bit": a_closes_loss_streak_cv_bit,
        "a_closes_win_streak_bit": a_closes_win_streak_bit,
        "a_closes_win_streak_max_bit": a_closes_win_streak_max_bit,
        "a_closes_win_streak_mean_bit": a_closes_win_streak_mean_bit,
        "a_closes_win_streak_median_bit": a_closes_win_streak_median_bit,
        "a_closes_win_streak_min_bit": a_closes_win_streak_min_bit,
        "a_closes_win_streak_stdev_bit": a_closes_win_streak_stdev_bit,
        "a_closes_win_streak_cv_bit": a_closes_win_streak_cv_bit,
        "a_closes_exit_mix_bit": a_closes_exit_mix_bit,
        "a_closes_exit_tp_share_bit": a_closes_exit_tp_share_bit,
        "a_closes_exit_sl_share_bit": a_closes_exit_sl_share_bit,
        "a_closes_exit_rot_share_bit": a_closes_exit_rot_share_bit,
        "a_closes_exit_trim_share_bit": a_closes_exit_trim_share_bit,
        "a_closes_exit_lead_bit": a_closes_exit_lead_bit,
        "a_closes_exit_euro_lead_bit": a_closes_exit_euro_lead_bit,
        "a_closes_exit_euro_offset_bit": a_closes_exit_euro_offset_bit,
        "a_closes_exit_euro_gap_bit": a_closes_exit_euro_gap_bit,
        "a_closes_exit_euro_conc_bit": a_closes_exit_euro_conc_bit,
        "a_closes_exit_euro_count_skew_bit": a_closes_exit_euro_count_skew_bit,
        "a_closes_exit_euro_size_bit": a_closes_exit_euro_size_bit,
        "a_closes_exit_euro_size_n_bit": a_closes_exit_euro_size_n_bit,
        "a_closes_exit_euro_size_rest_n_bit": a_closes_exit_euro_size_rest_n_bit,
        "a_closes_exit_euro_size_sign_bit": a_closes_exit_euro_size_sign_bit,
        "a_closes_exit_euro_size_rest_sign_bit": (
            a_closes_exit_euro_size_rest_sign_bit
        ),
        "a_closes_exit_euro_size_sign_clash_bit": (
            a_closes_exit_euro_size_sign_clash_bit
        ),
        "a_closes_exit_euro_size_sign_clash_net_bit": (
            a_closes_exit_euro_size_sign_clash_net_bit
        ),
        "a_closes_exit_euro_size_sign_clash_keep_bit": (
            a_closes_exit_euro_size_sign_clash_keep_bit
        ),
        "a_closes_exit_euro_size_sign_clash_keep_fees_bit": (
            a_closes_exit_euro_size_sign_clash_keep_fees_bit
        ),
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_bit": (
            a_closes_exit_euro_size_sign_clash_keep_fees_vs_bit
        ),
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_bit": (
            a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_bit
        ),
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_bit": (
            a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_bit
        ),
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_bit": (
            a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_bit
        ),
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_bit": (
            a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_bit
        ),
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit": (
            a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit
        ),
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_bit": (
            a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_bit
        ),
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_bit": (
            a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_bit
        ),
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_bit": (
            a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_bit
        ),
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size_bit": (
            a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size_bit
        ),
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_bit": (
            a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_bit
        ),
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_bit": (
            a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_bit
        ),
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_bit": (
            a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_bit
        ),
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_bit": (
            a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_bit
        ),
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_bit": (
            a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_bit
        ),
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_bit": (
            a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_bit
        ),
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_bit": (
            a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_bit
        ),
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit": (
            a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit
        ),
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size_bit": (
            a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size_bit
        ),
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_bit": (
            a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_bit
        ),
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_bit": (
            a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_bit
        ),
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_bit": (
            a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_bit
        ),
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_bit": (
            a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_bit
        ),
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_bit": (
            a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_bit
        ),
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta_bit": (
            a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta_bit
        ),
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_bit": (
            a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_bit
        ),
        "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit": (
            a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit
        ),
        "a_closes_exit_unknown_bit": a_closes_exit_unknown_bit,
        "a_closes_flat_bit": a_closes_flat_bit,
        "a_closes_payoff_bit": a_closes_payoff_bit,
        "a_closes_expectancy_bit": a_closes_expectancy_bit,
        "a_closes_net_expectancy_bit": a_closes_net_expectancy_bit,
        "a_closes_fee_take_bit": a_closes_fee_take_bit,
        "a_closes_net_vs_fee_bit": a_closes_net_vs_fee_bit,
        "a_closes_net_profit_factor_bit": a_closes_net_profit_factor_bit,
        "a_closes_profit_factor_bit": a_closes_profit_factor_bit,
        "b_ready": b_ready if window == "A" else True,
        "b_blockers": b_blockers if window == "A" else [],
        "b_block_bit": b_block_bit if window == "A" else "",
    }


def build_exit_policy_glance() -> dict[str, Any]:
    """Compact stock exit asymmetry line (portfolio AI / exit_policy; display only).

    Live stock exits are TP +8% / SL −5% / rotate ≥+5%. Designed reward:risk is
    TP/SL (8:5 → 1.6) — staskh RV-ratio docs adapted: state what the ratio is.
    Crypto uses wider bands (see crypto_policy glance). Not ATR stops; not a new
    entry gate.
    """
    from stock_checker.exit_policy import (
        DEFAULT_ROTATE_MIN_PROFIT_PCT,
        DEFAULT_STOP_LOSS_PCT,
        DEFAULT_TAKE_PROFIT_PCT,
    )

    tp = float(DEFAULT_TAKE_PROFIT_PCT)
    sl = float(DEFAULT_STOP_LOSS_PCT)
    rot = float(DEFAULT_ROTATE_MIN_PROFIT_PCT)
    designed_rr = round(tp / sl, 2) if sl > 0 else None
    if designed_rr is not None:
        line = (
            f"stocks TP +{tp:g}% · SL −{sl:g}% · "
            f"designed RR {designed_rr:g} · rotate ≥+{rot:g}%"
        )
    else:
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
        "designed_rr": designed_rr,
    }


def build_earnings_blackout_glance() -> dict[str, Any]:
    """Stock earnings blackout + empty-window fail-open (tradermonty; display only).

    New stock entries stay blocked DEFAULT_DAYS_BEFORE before and DEFAULT_DAYS_AFTER
    after earnings. The window uses the America/New_York date, not UTC
    (tradermonty #426). Crypto is exempt. Missing Yahoo date → allow (fail-open).
    Empty Yahoo ``earnings_dates`` with no calendar date is a *suspect* empty
    window (tradermonty #379) — still allow, but call it out (not a silent waiver).
    A nonempty payload or an ``Earnings Date`` cell with no usable date
    (epoch / junk) is ``malformed`` (xang1234 e433265) — still allow, not a
    successful “no earnings” lookup. Policy honesty only — no live calendar
    poll. Not a new gate.
    """
    from stock_checker.earnings_guard import (
        DEFAULT_DAYS_AFTER,
        DEFAULT_DAYS_BEFORE,
        EARNINGS_CLOCK,
    )

    before = float(DEFAULT_DAYS_BEFORE)
    after = float(DEFAULT_DAYS_AFTER)
    line = (
        f"stocks · NY date · {before:g}d/{after:g}d · "
        "empty/bad Yahoo → allow (suspect) · crypto exempt"
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
        "empty_window": "allow_suspect",
        "malformed": "allow_suspect",
        "clock": EARNINGS_CLOCK,
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


def build_atr_display_glance(
    rows: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Screener ATR / R:R honesty (RyanJHamby + staskh vol coverage; display only).

    Screener may show ~2×ATR stop notes. Missing vol → soft n/a on the note
    (not refuse). Live stock exits stay TP/SL via exit_policy — not ATR stops.
    Guardrail mirror — not a new gate.
    """
    from stock_checker.atr_risk import DEFAULT_ATR_MULT, atr_vol_coverage
    from stock_checker.exit_policy import (
        DEFAULT_STOP_LOSS_PCT,
        DEFAULT_TAKE_PROFIT_PCT,
    )

    mult = float(DEFAULT_ATR_MULT)
    tp = float(DEFAULT_TAKE_PROFIT_PCT)
    sl = float(DEFAULT_STOP_LOSS_PCT)
    cov = atr_vol_coverage(rows)
    total = int(cov.get("total") or 0)
    with_vol = int(cov.get("with_vol") or 0)
    missing = int(cov.get("missing") or 0)
    if total > 0:
        mid = (
            f"{with_vol}/{total} with vol"
            if missing == 0
            else f"{with_vol}/{total} with vol · {missing} soft n/a"
        )
        line = (
            f"ATR ~{mult:g}× · {mid} · "
            f"live TP +{tp:g}% / SL −{sl:g}% (not ATR)"
        )
        tone = "warn" if missing > 0 else "display"
    else:
        line = (
            f"Screener ATR ~{mult:g}× notes · display only · "
            f"live TP +{tp:g}% / SL −{sl:g}% (not ATR)"
        )
        tone = "display"
    if len(line) > 96:
        line = line[:95] + "…"
    return {
        "ready": True,
        "tone": tone,
        "line": line,
        "atr_mult": mult,
        "take_profit_pct": tp,
        "stop_loss_pct": sl,
        "live_atr_stops": False,
        "vol_total": total,
        "vol_with": with_vol,
        "vol_missing": missing,
        "vol_coverage_pct": cov.get("coverage_pct"),
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



# Warn when a buy-block / lock clears within one scan floor (tradermonty #398
# "warn before exception expiry" → desk cooldown honesty; display only).
DEFAULT_COOLDOWN_EXPIRY_WARN_SEC = 15 * 60


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


def _cooldown_expiring_soon(
    seconds_left: float,
    *,
    warn_seconds: float = DEFAULT_COOLDOWN_EXPIRY_WARN_SEC,
) -> bool:
    """True when a lock still active but clears within the warn window."""
    try:
        left = float(seconds_left)
        warn = float(warn_seconds)
    except (TypeError, ValueError):
        return False
    return warn > 0 and 0 < left <= warn


def build_rebuy_cooldown_glance(
    exit_times: dict[str, Any] | None,
    *,
    cooldown_seconds: float,
    now: float | None = None,
    expiry_warn_seconds: float = DEFAULT_COOLDOWN_EXPIRY_WARN_SEC,
) -> dict[str, Any]:
    """Compact anti flip-flop rebuy cooldown (tradermonty / SCHW; display only).

    After an exit, the same symbol stays blocked for min-hold seconds.
    Desk shows how many names are still cooling — not a new entry gate.
    Warns when the soonest lock clears within one scan interval.
    """
    empty = {
        "ready": False,
        "tone": "flat",
        "line": "",
        "cooling": 0,
        "cooldown_hours": 0.0,
        "symbols": [],
        "expiring_soon": False,
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
            "expiring_soon": False,
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
    soonest = cooling[0][1] if cooling else 0.0
    expiring = bool(cooling) and _cooldown_expiring_soon(
        soonest, warn_seconds=expiry_warn_seconds
    )
    if n == 0:
        tone = "clear"
        status = "clear"
    elif n >= 3:
        tone = "warn"
        status = f"{n} cooling"
    elif expiring:
        tone = "expiring"
        status = f"{n} cooling"
    else:
        tone = "cooling"
        status = f"{n} cooling"
    line = f"{status} · ≥{hold_txt} rebuy lock"
    if shown:
        line = f"{status} · {', '.join(shown)} · ≥{hold_txt} lock"
    if n >= 3:
        line = f"{line} · flip-flop pressure"
    if expiring:
        line = f"{line} · unlocks soon"
    if len(line) > 96:
        line = line[:95] + "…"
    return {
        "ready": True,
        "tone": tone,
        "line": line,
        "cooling": n,
        "cooldown_hours": hold_h,
        "symbols": [sym for sym, _ in cooling[:5]],
        "expiring_soon": expiring,
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
    max one crypto slot, wider ±10% exits (designed RR 1.0 — staskh ratio docs).
    Not a new entry gate.
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
    designed_rr = round(tp / sl, 2) if sl > 0 else None
    rr_bit = f" · RR {designed_rr:g}" if designed_rr is not None else ""
    line = f"{status} · BTC/ETH only · {exits}{rr_bit}"
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
        "designed_rr": designed_rr,
    }


def build_post_sl_cooldown_glance(
    last_sl_symbol: str | None,
    last_sl_epoch: float | None,
    *,
    cooldown_seconds: float | None = None,
    now: float | None = None,
    expiry_warn_seconds: float = DEFAULT_COOLDOWN_EXPIRY_WARN_SEC,
) -> dict[str, Any]:
    """Compact post-stop-loss buy cooldown (tradermonty anti-revenge; display only).

    After an SL sell, new buys stay blocked ≥4h (trader floor). Desk derives the
    window from trades.jsonl so pretrade WARN stays honest without in-memory state.
    Warns when the block clears within one scan interval (exception-expiry pattern).
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
        "expiring_soon": False,
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
            "expiring_soon": False,
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
            "expiring_soon": False,
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
            "expiring_soon": False,
        }
    left_txt = _fmt_cooldown_left(left)
    bit = f"{sym} " if sym else ""
    expiring = _cooldown_expiring_soon(left, warn_seconds=expiry_warn_seconds)
    if expiring:
        tone = "expiring"
        line = (
            f"EXPIRING · {bit}{left_txt} left · buys unlock soon · "
            f"≥{hold_txt} after SL"
        )
    else:
        tone = "active"
        line = f"ACTIVE · {bit}{left_txt} left · ≥{hold_txt} after SL — buys blocked"
    if len(line) > 96:
        line = line[:95] + "…"
    return {
        "ready": True,
        "tone": tone,
        "line": line,
        "symbol": sym,
        "active": True,
        "seconds_left": left,
        "cooldown_hours": hold_h,
        "expiring_soon": expiring,
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
    expiry_warn_seconds: float = DEFAULT_COOLDOWN_EXPIRY_WARN_SEC,
) -> dict[str, Any]:
    """Open lots still inside min-hold (portfolio AI / tradermonty; display only).

    Pairs with stuck-capital (underwater *after* unlock) and book-limits.
    Warns when the earliest lot unlocks within one scan interval.
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
        "expiring_soon": False,
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
            "expiring_soon": False,
        }
    locked_rows.sort(key=lambda t: t["left"])
    earliest = locked_rows[0]
    left_txt = _fmt_hold(float(earliest["left"]))
    expiring = _cooldown_expiring_soon(
        float(earliest["left"]), warn_seconds=expiry_warn_seconds
    )
    line = (
        f"{locked_n}/{timed_n} in min-hold lock ({hold_txt}) · "
        f"earliest {earliest['symbol']} {left_txt}"
    )
    if expiring:
        tone = "expiring"
        line = f"{line} · unlocks soon"
    elif locked_n == timed_n:
        tone = "warn"
    else:
        tone = "flat"
    if len(line) > 96:
        line = line[:95] + "…"
    return {
        "ready": True,
        "tone": tone,
        "line": line,
        "locked": locked_n,
        "timed": timed_n,
        "min_hold_hours": hold_h,
        "earliest_symbol": str(earliest["symbol"]),
        "earliest_left": left_txt,
        "expiring_soon": expiring,
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
    from stock_checker.runtime_pin import runtime_pin_status
    from stock_checker.trader_config import load_trader_config

    data_dir = Path(os.getenv("DATA_DIR", "/data"))
    cfg = load_trader_config(data_dir)
    py_pin = runtime_pin_status()

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
        "python_expected": py_pin["expected"],
        "python_running": py_pin["running"],
        "python_pin_ok": bool(py_pin["ok"]),
        "python_pin_line": py_pin["line"],
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


def breadth_run_covers_day(day: str, scan_time: Any) -> bool | None:
    """True when ``scan_time`` UTC date equals ``day``.

    ``None`` when ``scan_time`` is missing or unparseable (legacy fail-open).
    xang1234 stale-run metadata repair: a run must cover the ranking date.
    """
    day_s = str(day or "").strip()
    if len(day_s) != 10 or day_s[4] != "-" or day_s[7] != "-":
        return None
    dt = _parse_book_ts(scan_time)
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%d") == day_s


def build_breadth_day_meta(
    row: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Daily pulse metadata honesty (display only; not a gate).

    xang1234: warn when ``scan_time`` falls on a different UTC day than ``day``.
    tradermonty all-null caps adapted: warn when both sleeves have 0 priced names.
    Missing ``scan_time`` stays silent (legacy rows).
    """
    empty = {
        "ready": False,
        "tone": "flat",
        "severity": "",
        "bit": "",
        "line": "",
        "run_covers_day": None,
        "scan_day": "",
        "priced": 0,
    }
    if not isinstance(row, Mapping):
        return empty
    day = str(row.get("day") or "").strip()
    if not day:
        return empty
    scan_time = row.get("scan_time")
    covers = breadth_run_covers_day(day, scan_time)
    dt = _parse_book_ts(scan_time)
    scan_day = dt.strftime("%Y-%m-%d") if dt is not None else ""
    crypto_n = int(row.get("crypto_n") or 0)
    if crypto_n <= 0:
        crypto_n = int(row.get("crypto_up") or 0) + int(row.get("crypto_down") or 0)
    stock_n = int(row.get("stock_scan_n") or 0)
    if stock_n <= 0:
        stock_n = int(row.get("stock_scan_up") or 0) + int(
            row.get("stock_scan_down") or 0
        )
    priced = max(0, crypto_n) + max(0, stock_n)
    if covers is False:
        bit = f"meta mismatch · scan on {scan_day or '?'}"
        return {
            "ready": True,
            "tone": "warn",
            "severity": "mismatch",
            "bit": bit,
            "line": bit,
            "run_covers_day": False,
            "scan_day": scan_day,
            "priced": priced,
        }
    if priced <= 0:
        bit = "pulse empty · 0 priced"
        return {
            "ready": True,
            "tone": "warn",
            "severity": "empty",
            "bit": bit,
            "line": bit,
            "run_covers_day": covers,
            "scan_day": scan_day,
            "priced": 0,
        }
    return {
        "ready": True,
        "tone": "ok",
        "severity": "ok",
        "bit": "",
        "line": "",
        "run_covers_day": covers,
        "scan_day": scan_day,
        "priced": priced,
    }


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


def is_confirmed_thrust_day(
    mover_pct: float | None,
    near_high_pct: float | None,
    stock_adv_pct: float | None,
    crypto_adv_pct: float | None,
    *,
    thrust_min_pct: float = DEFAULT_BREADTH_THRUST_MIN_PCT,
    dual_min_pct: float = DEFAULT_DUAL_ADVANCE_MIN_PCT,
) -> bool:
    """True when thrust AND risk-on (dual advance). Scan-list; display only.

    StockBee-lite: movers + near-highs alone can fire on a split/weak tape.
    Confirmed thrust needs broad participation on both sleeves too.
    """
    return is_breadth_thrust_day(
        mover_pct, near_high_pct, min_pct=thrust_min_pct
    ) and is_dual_advance_day(
        stock_adv_pct, crypto_adv_pct, min_pct=dual_min_pct
    )


def is_unconfirmed_thrust_day(
    mover_pct: float | None,
    near_high_pct: float | None,
    stock_adv_pct: float | None,
    crypto_adv_pct: float | None,
    *,
    thrust_min_pct: float = DEFAULT_BREADTH_THRUST_MIN_PCT,
    dual_min_pct: float = DEFAULT_DUAL_ADVANCE_MIN_PCT,
) -> bool:
    """True when thrust fires without risk-on (thrust alone). Display only.

    StockBee-lite: repeated alone days are a false-thrust warning — movers
    + near-highs without dual-advance confirmation on both sleeves.
    """
    return is_breadth_thrust_day(
        mover_pct, near_high_pct, min_pct=thrust_min_pct
    ) and not is_dual_advance_day(
        stock_adv_pct, crypto_adv_pct, min_pct=dual_min_pct
    )


def thrust_confirm_rate_pct(
    confirmed_n: int, thrust_n: int
) -> float | None:
    """Share of thrust days that were risk-on confirmed. Display only.

    StockBee quality: alone thrust can look hot; confirm rate shows how often
    movers+near-high also had dual-advance. None when no thrust days yet.
    """
    t = int(thrust_n or 0)
    if t <= 0:
        return None
    c = max(0, int(confirmed_n or 0))
    return 100.0 * float(c) / float(t)


def thrust_density_pct(thrust_n: int, days: int) -> float | None:
    """Share of history days that were thrust days. Display only.

    StockBee heat frequency: confirm rate is quality of heat; density is how
    often the scan-list tape heats (±4% + near-high). None when no days yet.
    """
    d = int(days or 0)
    if d <= 0:
        return None
    t = max(0, int(thrust_n or 0))
    return 100.0 * float(t) / float(d)


def confirmed_density_pct(confirmed_n: int, days: int) -> float | None:
    """Share of history days that were confirmed thrust. Display only.

    StockBee: thrust density is any heat; confirmed density is clean heat
    (movers+near-high + risk-on). Reuses the same n/days math.
    """
    return thrust_density_pct(confirmed_n, days)


def alone_density_pct(alone_n: int, days: int) -> float | None:
    """Share of history days that were thrust-alone. Display only.

    StockBee false-thrust frequency: how often movers+near-high printed
    without dual-advance. Complements confirm rate (quality of thrust days).
    """
    return thrust_density_pct(alone_n, days)


def tape_label_density_pct(label_n: int, days: int) -> float | None:
    """Share of history days with a given tape label. Display only.

    StockBee tape frequency: risk-on / split / risk-off / mixed as % of
    scan-list history days. Same n/days math as thrust density.
    """
    return thrust_density_pct(label_n, days)


def tape_flip_density_pct(flip_n: int, pair_n: int) -> float | None:
    """Share of consecutive known-label day pairs that flipped. Display only.

    StockBee chop: label densities show how often each tape state appears;
    flip density shows how often the label *changes* day-to-day. Denominator
    is known→known pairs (both sleeves priced), not raw day count. None when
    fewer than two known labels in a row.
    """
    return thrust_density_pct(flip_n, pair_n)


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


def breadth_days_since_confirmed_thrust(
    rows: list[dict[str, Any]],
    *,
    thrust_min_pct: float = DEFAULT_BREADTH_THRUST_MIN_PCT,
    dual_min_pct: float = DEFAULT_DUAL_ADVANCE_MIN_PCT,
    through_day: str | None = None,
) -> int | None:
    """Days since last confirmed thrust (0 = now). Display only; scan-list."""
    return _breadth_days_since(
        rows,
        lambda r: _row_is_confirmed_thrust(
            r, thrust_min_pct=thrust_min_pct, dual_min_pct=dual_min_pct
        ),
        through_day=through_day,
    )


def breadth_days_since_unconfirmed_thrust(
    rows: list[dict[str, Any]],
    *,
    thrust_min_pct: float = DEFAULT_BREADTH_THRUST_MIN_PCT,
    dual_min_pct: float = DEFAULT_DUAL_ADVANCE_MIN_PCT,
    through_day: str | None = None,
) -> int | None:
    """Days since last thrust-alone day (0 = now). Display only; scan-list.

    StockBee-lite: after the tape recovers, friends need false-thrust
    staleness — how long since movers+near-high printed without risk-on.
    """
    return _breadth_days_since(
        rows,
        lambda r: _row_is_unconfirmed_thrust(
            r, thrust_min_pct=thrust_min_pct, dual_min_pct=dual_min_pct
        ),
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


def breadth_days_since_tape_split(
    rows: list[dict[str, Any]],
    *,
    strong_pct: float = DEFAULT_TAPE_SPLIT_STRONG_PCT,
    weak_pct: float = DEFAULT_TAPE_SPLIT_WEAK_PCT,
    through_day: str | None = None,
) -> int | None:
    """Days since last tape-split (0 = now). Display only; scan-list history.

    StockBee-lite: when sleeves re-align, friends need divergence staleness —
    how long since one sleeve ran hot while the other lagged — not only
    ending split streaks.
    """
    return _breadth_days_since(
        rows,
        lambda r: _row_is_tape_split(
            r, strong_pct=strong_pct, weak_pct=weak_pct
        ),
        through_day=through_day,
    )


def breadth_days_since_mixed(
    rows: list[dict[str, Any]],
    *,
    dual_min_pct: float = DEFAULT_DUAL_ADVANCE_MIN_PCT,
    strong_pct: float = DEFAULT_TAPE_SPLIT_STRONG_PCT,
    weak_pct: float = DEFAULT_TAPE_SPLIT_WEAK_PCT,
    risk_off_max_pct: float = DEFAULT_RISK_OFF_MAX_PCT,
    through_day: str | None = None,
) -> int | None:
    """Days since last mixed tape (0 = now). Display only; scan-list history.

    StockBee-lite: when the tape leaves chop, friends need mid-range
    staleness — how long since both sleeves were priced but neither
    risk-on, split, nor risk-off — completing days-since for all labels.
    """
    return _breadth_days_since(
        rows,
        lambda r: _row_is_mixed(
            r,
            dual_min_pct=dual_min_pct,
            strong_pct=strong_pct,
            weak_pct=weak_pct,
            risk_off_max_pct=risk_off_max_pct,
        ),
        through_day=through_day,
    )


def _breadth_tape_labels(
    rows: list[dict[str, Any]],
    *,
    through_day: str | None = None,
    dual_min_pct: float = DEFAULT_DUAL_ADVANCE_MIN_PCT,
    strong_pct: float = DEFAULT_TAPE_SPLIT_STRONG_PCT,
    weak_pct: float = DEFAULT_TAPE_SPLIT_WEAK_PCT,
    risk_off_max_pct: float = DEFAULT_RISK_OFF_MAX_PCT,
) -> list[str] | None:
    """Chronological tape labels through newest (or through_day). Display only.

    ``None`` when ``through_day`` is set but missing from rows.
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
    return [
        _row_tape_label(
            r,
            dual_min_pct=dual_min_pct,
            strong_pct=strong_pct,
            weak_pct=weak_pct,
            risk_off_max_pct=risk_off_max_pct,
        )
        for r in usable
    ]


def breadth_days_since_tape_flip(
    rows: list[dict[str, Any]],
    *,
    through_day: str | None = None,
    dual_min_pct: float = DEFAULT_DUAL_ADVANCE_MIN_PCT,
    strong_pct: float = DEFAULT_TAPE_SPLIT_STRONG_PCT,
    weak_pct: float = DEFAULT_TAPE_SPLIT_WEAK_PCT,
    risk_off_max_pct: float = DEFAULT_RISK_OFF_MAX_PCT,
) -> int | None:
    """Days since last known→known tape flip (0 = newest day flipped). Display only.

    StockBee + tradermonty: flip density shows chop frequency; days-since flip
    shows how long the label has been stable after the last change. Pair-aware
    (needs prior day). ``None`` when no flip in history (or fewer than two
    known labels in a row).
    """
    labels = _breadth_tape_labels(
        rows,
        through_day=through_day,
        dual_min_pct=dual_min_pct,
        strong_pct=strong_pct,
        weak_pct=weak_pct,
        risk_off_max_pct=risk_off_max_pct,
    )
    if labels is None or len(labels) < 2:
        return None
    for i in range(len(labels) - 1, 0, -1):
        if is_tape_flip(labels[i - 1], labels[i]):
            return len(labels) - 1 - i
    return None


def breadth_tape_flip_streak(
    rows: list[dict[str, Any]],
    *,
    through_day: str | None = None,
    dual_min_pct: float = DEFAULT_DUAL_ADVANCE_MIN_PCT,
    strong_pct: float = DEFAULT_TAPE_SPLIT_STRONG_PCT,
    weak_pct: float = DEFAULT_TAPE_SPLIT_WEAK_PCT,
    risk_off_max_pct: float = DEFAULT_RISK_OFF_MAX_PCT,
) -> int:
    """Consecutive known→known flips ending at newest. Display only.

    StockBee chop storm: flip density = history rate; days-since flip = settle
    length; ending flip streak = how many label changes in a row right now.
    0 when newest day did not flip (or fewer than two known labels).
    """
    labels = _breadth_tape_labels(
        rows,
        through_day=through_day,
        dual_min_pct=dual_min_pct,
        strong_pct=strong_pct,
        weak_pct=weak_pct,
        risk_off_max_pct=risk_off_max_pct,
    )
    if labels is None or len(labels) < 2:
        return 0
    streak = 0
    for i in range(len(labels) - 1, 0, -1):
        if is_tape_flip(labels[i - 1], labels[i]):
            streak += 1
        else:
            break
    return streak


def _breadth_tape_flip_run_lengths(labels: list[str]) -> list[int]:
    """Lengths of consecutive known→known flip runs. Empty when no flips."""
    if len(labels) < 2:
        return []
    runs: list[int] = []
    run = 0
    for i in range(1, len(labels)):
        if is_tape_flip(labels[i - 1], labels[i]):
            run += 1
        elif run:
            runs.append(run)
            run = 0
    if run:
        runs.append(run)
    return runs


def breadth_tape_flip_max_streak(
    rows: list[dict[str, Any]],
    *,
    through_day: str | None = None,
    dual_min_pct: float = DEFAULT_DUAL_ADVANCE_MIN_PCT,
    strong_pct: float = DEFAULT_TAPE_SPLIT_STRONG_PCT,
    weak_pct: float = DEFAULT_TAPE_SPLIT_WEAK_PCT,
    risk_off_max_pct: float = DEFAULT_RISK_OFF_MAX_PCT,
) -> int:
    """Longest consecutive known→known flip run in history. Display only.

    StockBee peak chop: ending flip streak = storm now; max flip streak = worst
    storm in the window (pairs with flip dens / days-since settle). 0 when no
    flips (or fewer than two known labels).
    """
    labels = _breadth_tape_labels(
        rows,
        through_day=through_day,
        dual_min_pct=dual_min_pct,
        strong_pct=strong_pct,
        weak_pct=weak_pct,
        risk_off_max_pct=risk_off_max_pct,
    )
    if labels is None:
        return 0
    runs = _breadth_tape_flip_run_lengths(labels)
    return max(runs) if runs else 0


def breadth_tape_flip_mean_streak(
    rows: list[dict[str, Any]],
    *,
    through_day: str | None = None,
    dual_min_pct: float = DEFAULT_DUAL_ADVANCE_MIN_PCT,
    strong_pct: float = DEFAULT_TAPE_SPLIT_STRONG_PCT,
    weak_pct: float = DEFAULT_TAPE_SPLIT_WEAK_PCT,
    risk_off_max_pct: float = DEFAULT_RISK_OFF_MAX_PCT,
) -> float | None:
    """Mean length of consecutive flip runs in history. Display only.

    StockBee typical chop: ending streak = storm now; max = peak storm; mean =
    average storm size across runs (pairs with flip dens / days-since settle).
    ``None`` when no flip runs (or fewer than two known labels).
    """
    labels = _breadth_tape_labels(
        rows,
        through_day=through_day,
        dual_min_pct=dual_min_pct,
        strong_pct=strong_pct,
        weak_pct=weak_pct,
        risk_off_max_pct=risk_off_max_pct,
    )
    if labels is None:
        return None
    runs = _breadth_tape_flip_run_lengths(labels)
    if not runs:
        return None
    return sum(runs) / len(runs)


def breadth_tape_flip_median_streak(
    rows: list[dict[str, Any]],
    *,
    through_day: str | None = None,
    dual_min_pct: float = DEFAULT_DUAL_ADVANCE_MIN_PCT,
    strong_pct: float = DEFAULT_TAPE_SPLIT_STRONG_PCT,
    weak_pct: float = DEFAULT_TAPE_SPLIT_WEAK_PCT,
    risk_off_max_pct: float = DEFAULT_RISK_OFF_MAX_PCT,
) -> float | None:
    """Median length of consecutive flip runs in history. Display only.

    StockBee robust typical chop: mean can be pulled by one long storm; median
    resists that (pairs with avg / max / ending streak). ``None`` when no flip
    runs (or fewer than two known labels).
    """
    labels = _breadth_tape_labels(
        rows,
        through_day=through_day,
        dual_min_pct=dual_min_pct,
        strong_pct=strong_pct,
        weak_pct=weak_pct,
        risk_off_max_pct=risk_off_max_pct,
    )
    if labels is None:
        return None
    runs = _breadth_tape_flip_run_lengths(labels)
    if not runs:
        return None
    ordered = sorted(runs)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def breadth_tape_flip_min_streak(
    rows: list[dict[str, Any]],
    *,
    through_day: str | None = None,
    dual_min_pct: float = DEFAULT_DUAL_ADVANCE_MIN_PCT,
    strong_pct: float = DEFAULT_TAPE_SPLIT_STRONG_PCT,
    weak_pct: float = DEFAULT_TAPE_SPLIT_WEAK_PCT,
    risk_off_max_pct: float = DEFAULT_RISK_OFF_MAX_PCT,
) -> int:
    """Shortest consecutive known→known flip run in history. Display only.

    StockBee floor chop: max = peak storm; min = mildest storm in the window
    (pairs with avg / med when storms vary). 0 when no flips (or fewer than two
    known labels).
    """
    labels = _breadth_tape_labels(
        rows,
        through_day=through_day,
        dual_min_pct=dual_min_pct,
        strong_pct=strong_pct,
        weak_pct=weak_pct,
        risk_off_max_pct=risk_off_max_pct,
    )
    if labels is None:
        return 0
    runs = _breadth_tape_flip_run_lengths(labels)
    return min(runs) if runs else 0


def breadth_tape_flip_stdev_streak(
    rows: list[dict[str, Any]],
    *,
    through_day: str | None = None,
    dual_min_pct: float = DEFAULT_DUAL_ADVANCE_MIN_PCT,
    strong_pct: float = DEFAULT_TAPE_SPLIT_STRONG_PCT,
    weak_pct: float = DEFAULT_TAPE_SPLIT_WEAK_PCT,
    risk_off_max_pct: float = DEFAULT_RISK_OFF_MAX_PCT,
) -> float | None:
    """Sample stdev of consecutive flip-run lengths. Display only.

    StockBee chop dispersion: min/max = floor/peak; mean/med = typical; σ =
    how uneven storm sizes are (sample n−1). ``None`` when fewer than two flip
    runs (or fewer than two known labels).
    """
    labels = _breadth_tape_labels(
        rows,
        through_day=through_day,
        dual_min_pct=dual_min_pct,
        strong_pct=strong_pct,
        weak_pct=weak_pct,
        risk_off_max_pct=risk_off_max_pct,
    )
    if labels is None:
        return None
    runs = _breadth_tape_flip_run_lengths(labels)
    if len(runs) < 2:
        return None
    mean = sum(runs) / len(runs)
    var = sum((r - mean) ** 2 for r in runs) / (len(runs) - 1)
    return var**0.5


def breadth_tape_flip_cv_streak(
    rows: list[dict[str, Any]],
    *,
    through_day: str | None = None,
    dual_min_pct: float = DEFAULT_DUAL_ADVANCE_MIN_PCT,
    strong_pct: float = DEFAULT_TAPE_SPLIT_STRONG_PCT,
    weak_pct: float = DEFAULT_TAPE_SPLIT_WEAK_PCT,
    risk_off_max_pct: float = DEFAULT_RISK_OFF_MAX_PCT,
) -> float | None:
    """Coefficient of variation of flip-run lengths (σ / mean). Display only.

    StockBee relative chop: σ is absolute storm-size spread; CV scales by the
    typical storm (pairs with σ / avg). ``None`` when σ missing or mean ≤ 0.
    """
    stdev = breadth_tape_flip_stdev_streak(
        rows,
        through_day=through_day,
        dual_min_pct=dual_min_pct,
        strong_pct=strong_pct,
        weak_pct=weak_pct,
        risk_off_max_pct=risk_off_max_pct,
    )
    if stdev is None:
        return None
    mean = breadth_tape_flip_mean_streak(
        rows,
        through_day=through_day,
        dual_min_pct=dual_min_pct,
        strong_pct=strong_pct,
        weak_pct=weak_pct,
        risk_off_max_pct=risk_off_max_pct,
    )
    if mean is None or mean <= 0:
        return None
    return stdev / mean


def breadth_tape_flip_run_count(
    rows: list[dict[str, Any]],
    *,
    through_day: str | None = None,
    dual_min_pct: float = DEFAULT_DUAL_ADVANCE_MIN_PCT,
    strong_pct: float = DEFAULT_TAPE_SPLIT_STRONG_PCT,
    weak_pct: float = DEFAULT_TAPE_SPLIT_WEAK_PCT,
    risk_off_max_pct: float = DEFAULT_RISK_OFF_MAX_PCT,
) -> int:
    """Number of distinct consecutive flip runs in history. Display only."""
    labels = _breadth_tape_labels(
        rows,
        through_day=through_day,
        dual_min_pct=dual_min_pct,
        strong_pct=strong_pct,
        weak_pct=weak_pct,
        risk_off_max_pct=risk_off_max_pct,
    )
    if labels is None:
        return 0
    return len(_breadth_tape_flip_run_lengths(labels))


def format_flip_run_chop_bits(
    *,
    flip_streak: int = 0,
    flip_max_streak: int = 0,
    flip_min_streak: int = 0,
    flip_mean_streak: float | None = None,
    flip_median_streak: float | None = None,
    flip_stdev_streak: float | None = None,
    flip_cv_streak: float | None = None,
    flip_run_n: int = 0,
) -> list[str]:
    """Flip-run distribution bits for Breadth chop details (display only).

    MonsterDeveloper + xang1234: keep live flip / days-since / dens on the
    primary glance; park max/avg/med/min/σ/CV under a details fold so the
    desk stays short. Not a gate.
    """
    bits: list[str] = []
    if flip_max_streak >= 2 and flip_max_streak > flip_streak:
        bits.append(f"max flip {flip_max_streak}")
    if flip_mean_streak is not None and flip_run_n >= 2:
        bits.append(f"avg flip {flip_mean_streak:.1f} ({flip_run_n} runs)")
    if (
        flip_median_streak is not None
        and flip_run_n >= 3
        and (
            flip_mean_streak is None
            or abs(flip_median_streak - flip_mean_streak) >= 0.05
        )
    ):
        bits.append(f"med flip {flip_median_streak:.1f}")
    if (
        flip_run_n >= 2
        and flip_min_streak > 0
        and flip_min_streak < flip_max_streak
    ):
        bits.append(f"min flip {flip_min_streak}")
    if (
        flip_stdev_streak is not None
        and flip_run_n >= 3
        and flip_stdev_streak >= 0.05
    ):
        bits.append(f"σ flip {flip_stdev_streak:.1f}")
    if (
        flip_cv_streak is not None
        and flip_run_n >= 3
        and flip_cv_streak >= 0.05
    ):
        bits.append(f"CV flip {flip_cv_streak:.1f}")
    return bits


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


def _row_is_confirmed_thrust(
    row: dict[str, Any],
    *,
    thrust_min_pct: float = DEFAULT_BREADTH_THRUST_MIN_PCT,
    dual_min_pct: float = DEFAULT_DUAL_ADVANCE_MIN_PCT,
) -> bool:
    """Resolve confirmed thrust (thrust + risk-on) from pulse row."""
    if "is_confirmed_thrust" in row:
        return bool(row.get("is_confirmed_thrust"))
    return _row_is_thrust(row, min_pct=thrust_min_pct) and _row_is_dual_advance(
        row, min_pct=dual_min_pct
    )


def _row_is_unconfirmed_thrust(
    row: dict[str, Any],
    *,
    thrust_min_pct: float = DEFAULT_BREADTH_THRUST_MIN_PCT,
    dual_min_pct: float = DEFAULT_DUAL_ADVANCE_MIN_PCT,
) -> bool:
    """Resolve thrust-alone (thrust without risk-on) from pulse row."""
    if "is_unconfirmed_thrust" in row:
        return bool(row.get("is_unconfirmed_thrust"))
    return _row_is_thrust(row, min_pct=thrust_min_pct) and not _row_is_confirmed_thrust(
        row, thrust_min_pct=thrust_min_pct, dual_min_pct=dual_min_pct
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


def breadth_confirmed_thrust_streak(
    rows: list[dict[str, Any]],
    *,
    thrust_min_pct: float = DEFAULT_BREADTH_THRUST_MIN_PCT,
    dual_min_pct: float = DEFAULT_DUAL_ADVANCE_MIN_PCT,
    through_day: str | None = None,
) -> int:
    """Consecutive confirmed-thrust days ending at newest. Display only."""
    return _breadth_ending_streak(
        rows,
        lambda r: _row_is_confirmed_thrust(
            r, thrust_min_pct=thrust_min_pct, dual_min_pct=dual_min_pct
        ),
        through_day=through_day,
    )


def breadth_unconfirmed_thrust_streak(
    rows: list[dict[str, Any]],
    *,
    thrust_min_pct: float = DEFAULT_BREADTH_THRUST_MIN_PCT,
    dual_min_pct: float = DEFAULT_DUAL_ADVANCE_MIN_PCT,
    through_day: str | None = None,
) -> int:
    """Consecutive thrust-alone days ending at newest. Display only.

    StockBee-lite: ending alone streak warns when raw thrust keeps printing
    without dual-advance confirmation (not the same as any-thrust streak).
    """
    return _breadth_ending_streak(
        rows,
        lambda r: _row_is_unconfirmed_thrust(
            r, thrust_min_pct=thrust_min_pct, dual_min_pct=dual_min_pct
        ),
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


def breadth_mixed_streak(
    rows: list[dict[str, Any]],
    *,
    dual_min_pct: float = DEFAULT_DUAL_ADVANCE_MIN_PCT,
    strong_pct: float = DEFAULT_TAPE_SPLIT_STRONG_PCT,
    weak_pct: float = DEFAULT_TAPE_SPLIT_WEAK_PCT,
    risk_off_max_pct: float = DEFAULT_RISK_OFF_MAX_PCT,
    through_day: str | None = None,
) -> int:
    """Consecutive mixed (mid-range) days ending at newest. Display only."""
    return _breadth_ending_streak(
        rows,
        lambda r: _row_is_mixed(
            r,
            dual_min_pct=dual_min_pct,
            strong_pct=strong_pct,
            weak_pct=weak_pct,
            risk_off_max_pct=risk_off_max_pct,
        ),
        through_day=through_day,
    )


def build_breadth_thrust_summary(
    rows: list[dict[str, Any]],
    *,
    min_pct: float = DEFAULT_BREADTH_THRUST_MIN_PCT,
    dual_min_pct: float = DEFAULT_DUAL_ADVANCE_MIN_PCT,
) -> dict[str, Any]:
    """Count recent scan-list thrust days + ending streak. Display only.

    Separates raw thrust from StockBee **confirmed** thrust (thrust + risk-on)
    and **alone** thrust (thrust without risk-on — false-thrust warning).
    """
    days = 0
    thrust_n = 0
    confirmed_n = 0
    alone_n = 0
    latest = False
    latest_confirmed = False
    latest_alone = False
    for r in rows:
        if not isinstance(r, dict):
            continue
        flag = _row_is_thrust(r, min_pct=min_pct)
        confirmed = _row_is_confirmed_thrust(
            r, thrust_min_pct=min_pct, dual_min_pct=dual_min_pct
        )
        alone = _row_is_unconfirmed_thrust(
            r, thrust_min_pct=min_pct, dual_min_pct=dual_min_pct
        )
        days += 1
        if flag:
            thrust_n += 1
            latest = True
        else:
            latest = False
        if confirmed:
            confirmed_n += 1
            latest_confirmed = True
        else:
            latest_confirmed = False
        if alone:
            alone_n += 1
            latest_alone = True
        else:
            latest_alone = False
    empty = {
        "ready": False,
        "days": 0,
        "thrust_n": 0,
        "confirmed_n": 0,
        "alone_n": 0,
        "confirm_rate_pct": None,
        "density_pct": None,
        "confirmed_density_pct": None,
        "alone_density_pct": None,
        "streak": 0,
        "confirmed_streak": 0,
        "alone_streak": 0,
        "days_since": None,
        "days_since_confirmed": None,
        "days_since_alone": None,
        "latest": False,
        "latest_confirmed": False,
        "latest_alone": False,
        "min_pct": float(min_pct),
        "line": "",
        "tone": "flat",
    }
    if days <= 0:
        return empty
    streak = breadth_thrust_streak(rows, min_pct=min_pct)
    confirmed_streak = breadth_confirmed_thrust_streak(
        rows, thrust_min_pct=min_pct, dual_min_pct=dual_min_pct
    )
    alone_streak = breadth_unconfirmed_thrust_streak(
        rows, thrust_min_pct=min_pct, dual_min_pct=dual_min_pct
    )
    days_since = breadth_days_since_thrust(rows, min_pct=min_pct)
    days_since_confirmed = breadth_days_since_confirmed_thrust(
        rows, thrust_min_pct=min_pct, dual_min_pct=dual_min_pct
    )
    days_since_alone = breadth_days_since_unconfirmed_thrust(
        rows, thrust_min_pct=min_pct, dual_min_pct=dual_min_pct
    )
    confirm_rate = thrust_confirm_rate_pct(confirmed_n, thrust_n)
    density = thrust_density_pct(thrust_n, days)
    conf_density = confirmed_density_pct(confirmed_n, days)
    alone_density = alone_density_pct(alone_n, days)
    if latest_confirmed:
        tone = "up"
    elif latest_alone or latest or thrust_n:
        tone = "flat"
    else:
        tone = "down"
    bits: list[str] = []
    if latest_confirmed:
        bits.append("confirmed thrust now")
        if confirmed_streak >= 2:
            bits.append(f"confirmed streak {confirmed_streak}")
    elif latest_alone or latest:
        bits.append("thrust alone (not risk-on)")
        if alone_streak >= 2:
            bits.append(f"alone streak {alone_streak}")
        elif streak >= 2:
            bits.append(f"streak {streak}")
    else:
        if days_since_confirmed is not None and days_since_confirmed > 0:
            bits.append(f"{days_since_confirmed}d since confirmed")
        elif days_since_alone is not None and days_since_alone > 0:
            bits.append(f"{days_since_alone}d since alone")
        elif days_since is not None and days_since > 0:
            bits.append(f"{days_since}d since thrust")
        if alone_streak >= 2:
            bits.append(f"alone streak {alone_streak}")
        elif streak >= 2:
            bits.append(f"streak {streak}")
    if confirm_rate is not None:
        bits.append(
            f"confirm {confirm_rate:.0f}% ({confirmed_n}/{thrust_n} thrust)"
        )
    if density is not None:
        bits.append(f"density {density:.0f}% ({thrust_n}/{days} days)")
    if conf_density is not None:
        bits.append(
            f"confirmed dens {conf_density:.0f}% ({confirmed_n}/{days})"
        )
    if alone_density is not None:
        bits.append(f"alone dens {alone_density:.0f}% ({alone_n}/{days})")
    bits.append(
        f"{confirmed_n}/{days} confirmed · {alone_n}/{days} alone · "
        f"{thrust_n}/{days} thrust days "
        f"(≥{min_pct:.0f}% ±4% + near-high)"
    )
    return {
        "ready": True,
        "days": days,
        "thrust_n": thrust_n,
        "confirmed_n": confirmed_n,
        "alone_n": alone_n,
        "confirm_rate_pct": confirm_rate,
        "density_pct": density,
        "confirmed_density_pct": conf_density,
        "alone_density_pct": alone_density,
        "streak": streak,
        "confirmed_streak": confirmed_streak,
        "alone_streak": alone_streak,
        "days_since": days_since,
        "days_since_confirmed": days_since_confirmed,
        "days_since_alone": days_since_alone,
        "latest": latest,
        "latest_confirmed": latest_confirmed,
        "latest_alone": latest_alone,
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
    flip_n = 0
    pair_n = 0
    prev_label_for_flip = ""
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
        if str(prev_label_for_flip or "").strip() and str(label or "").strip():
            pair_n += 1
            if is_tape_flip(prev_label_for_flip, label):
                flip_n += 1
        prev_label_for_flip = label
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
        "risk_on_density_pct": None,
        "split_density_pct": None,
        "risk_off_density_pct": None,
        "mixed_density_pct": None,
        "flip_n": 0,
        "pair_n": 0,
        "flip_density_pct": None,
        "dual_streak": 0,
        "split_streak": 0,
        "risk_off_streak": 0,
        "mixed_streak": 0,
        "days_since_risk_on": None,
        "days_since_risk_off": None,
        "days_since_tape_split": None,
        "days_since_mixed": None,
        "days_since_tape_flip": None,
        "flip_streak": 0,
        "flip_max_streak": 0,
        "flip_min_streak": 0,
        "flip_mean_streak": None,
        "flip_median_streak": None,
        "flip_stdev_streak": None,
        "flip_cv_streak": None,
        "flip_run_n": 0,
        "chop_line": "",
        "chop_ready": False,
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
    mixed_streak = breadth_mixed_streak(
        rows,
        dual_min_pct=dual_min_pct,
        strong_pct=strong_pct,
        weak_pct=weak_pct,
        risk_off_max_pct=risk_off_max_pct,
    )
    days_since_risk_on = breadth_days_since_risk_on(rows, min_pct=dual_min_pct)
    days_since_risk_off = breadth_days_since_risk_off(
        rows, max_pct=risk_off_max_pct
    )
    days_since_tape_split = breadth_days_since_tape_split(
        rows, strong_pct=strong_pct, weak_pct=weak_pct
    )
    days_since_mixed = breadth_days_since_mixed(
        rows,
        dual_min_pct=dual_min_pct,
        strong_pct=strong_pct,
        weak_pct=weak_pct,
        risk_off_max_pct=risk_off_max_pct,
    )
    days_since_tape_flip = breadth_days_since_tape_flip(
        rows,
        dual_min_pct=dual_min_pct,
        strong_pct=strong_pct,
        weak_pct=weak_pct,
        risk_off_max_pct=risk_off_max_pct,
    )
    flip_streak = breadth_tape_flip_streak(
        rows,
        dual_min_pct=dual_min_pct,
        strong_pct=strong_pct,
        weak_pct=weak_pct,
        risk_off_max_pct=risk_off_max_pct,
    )
    flip_max_streak = breadth_tape_flip_max_streak(
        rows,
        dual_min_pct=dual_min_pct,
        strong_pct=strong_pct,
        weak_pct=weak_pct,
        risk_off_max_pct=risk_off_max_pct,
    )
    flip_mean_streak = breadth_tape_flip_mean_streak(
        rows,
        dual_min_pct=dual_min_pct,
        strong_pct=strong_pct,
        weak_pct=weak_pct,
        risk_off_max_pct=risk_off_max_pct,
    )
    flip_median_streak = breadth_tape_flip_median_streak(
        rows,
        dual_min_pct=dual_min_pct,
        strong_pct=strong_pct,
        weak_pct=weak_pct,
        risk_off_max_pct=risk_off_max_pct,
    )
    flip_min_streak = breadth_tape_flip_min_streak(
        rows,
        dual_min_pct=dual_min_pct,
        strong_pct=strong_pct,
        weak_pct=weak_pct,
        risk_off_max_pct=risk_off_max_pct,
    )
    flip_stdev_streak = breadth_tape_flip_stdev_streak(
        rows,
        dual_min_pct=dual_min_pct,
        strong_pct=strong_pct,
        weak_pct=weak_pct,
        risk_off_max_pct=risk_off_max_pct,
    )
    flip_cv_streak = breadth_tape_flip_cv_streak(
        rows,
        dual_min_pct=dual_min_pct,
        strong_pct=strong_pct,
        weak_pct=weak_pct,
        risk_off_max_pct=risk_off_max_pct,
    )
    flip_run_n = breadth_tape_flip_run_count(
        rows,
        dual_min_pct=dual_min_pct,
        strong_pct=strong_pct,
        weak_pct=weak_pct,
        risk_off_max_pct=risk_off_max_pct,
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
        if mixed_streak >= 2:
            bits.append(f"streak {mixed_streak}")
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
    if (
        not latest_split
        and days_since_tape_split is not None
        and days_since_tape_split > 0
    ):
        bits.append(f"{days_since_tape_split}d since split")
    if (
        not latest_mixed
        and days_since_mixed is not None
        and days_since_mixed > 0
    ):
        bits.append(f"{days_since_mixed}d since mixed")
    if flip:
        bits.append(f"flipped {prev_label}→{latest_label}")
        if flip_streak >= 2:
            bits.append(f"flip streak {flip_streak}")
    elif (
        days_since_tape_flip is not None
        and days_since_tape_flip > 0
    ):
        bits.append(f"{days_since_tape_flip}d since flip")
    # Distribution bits live on chop_line (Breadth details), not primary line.
    chop_bits = format_flip_run_chop_bits(
        flip_streak=flip_streak,
        flip_max_streak=flip_max_streak,
        flip_min_streak=flip_min_streak,
        flip_mean_streak=flip_mean_streak,
        flip_median_streak=flip_median_streak,
        flip_stdev_streak=flip_stdev_streak,
        flip_cv_streak=flip_cv_streak,
        flip_run_n=flip_run_n,
    )
    risk_on_density = tape_label_density_pct(dual_n, days)
    split_density = tape_label_density_pct(split_n, days)
    risk_off_density = tape_label_density_pct(risk_off_n, days)
    mixed_density = tape_label_density_pct(mixed_n, days)
    flip_density = tape_flip_density_pct(flip_n, pair_n)
    if risk_on_density is not None:
        bits.append(f"risk-on dens {risk_on_density:.0f}% ({dual_n}/{days})")
    if split_density is not None:
        bits.append(f"split dens {split_density:.0f}% ({split_n}/{days})")
    if risk_off_density is not None:
        bits.append(f"risk-off dens {risk_off_density:.0f}% ({risk_off_n}/{days})")
    if mixed_density is not None:
        bits.append(f"mixed dens {mixed_density:.0f}% ({mixed_n}/{days})")
    if flip_density is not None:
        bits.append(f"flip dens {flip_density:.0f}% ({flip_n}/{pair_n})")
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
        "risk_on_density_pct": risk_on_density,
        "split_density_pct": split_density,
        "risk_off_density_pct": risk_off_density,
        "mixed_density_pct": mixed_density,
        "flip_n": flip_n,
        "pair_n": pair_n,
        "flip_density_pct": flip_density,
        "dual_streak": dual_streak,
        "split_streak": split_streak,
        "risk_off_streak": risk_off_streak,
        "mixed_streak": mixed_streak,
        "days_since_risk_on": days_since_risk_on,
        "days_since_risk_off": days_since_risk_off,
        "days_since_tape_split": days_since_tape_split,
        "days_since_mixed": days_since_mixed,
        "days_since_tape_flip": days_since_tape_flip,
        "flip_streak": flip_streak,
        "flip_max_streak": flip_max_streak,
        "flip_min_streak": flip_min_streak,
        "flip_mean_streak": flip_mean_streak,
        "flip_median_streak": flip_median_streak,
        "flip_stdev_streak": flip_stdev_streak,
        "flip_cv_streak": flip_cv_streak,
        "flip_run_n": flip_run_n,
        "chop_line": " · ".join(chop_bits),
        "chop_ready": bool(chop_bits),
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
        row["is_confirmed_thrust"] = bool(row["is_thrust"] and row["is_dual_advance"])
        row["is_unconfirmed_thrust"] = bool(
            row["is_thrust"] and not row["is_dual_advance"]
        )
        meta = build_breadth_day_meta(row)
        row["meta_severity"] = str(meta.get("severity") or "")
        row["meta_tone"] = str(meta.get("tone") or "flat")
        row["meta_bit"] = str(meta.get("bit") or "")
        row["run_covers_day"] = meta.get("run_covers_day")
        row["meta_scan_day"] = str(meta.get("scan_day") or "")
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
            out = dict(row)
            meta = build_breadth_day_meta(out)
            out["meta_severity"] = str(meta.get("severity") or "")
            out["meta_tone"] = str(meta.get("tone") or "flat")
            out["meta_bit"] = str(meta.get("bit") or "")
            out["run_covers_day"] = meta.get("run_covers_day")
            out["meta_scan_day"] = str(meta.get("scan_day") or "")
            return out
    return None


def build_breadth_glance(
    pulse: dict[str, Any] | None,
    *,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """One-line scan-list glance for HTML screens + Charts API (display only; not a gate).

    tradermonty “verified estimate snapshots” + xang1234: show priced counts and
    label the pulse as a scan-list **estimate**, never full-universe A/D.
    Optional ``history`` adds StockBee thrust/risk-on/risk-off/split streak and
    days-since when the ending day is quiet.

    Day-run meta (xang1234 stale-run coverage + tradermonty all-null): when
    ``scan_time`` misses the pulse UTC day or both sleeves are 0 priced, speak
    the same ``meta mismatch`` / ``pulse empty`` bit on every screen — not only
    Breadth Recent days / scan-log. Meta warn overrides A/D tone.
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
        "is_confirmed_thrust": False,
        "is_unconfirmed_thrust": False,
        "thrust_streak": 0,
        "confirmed_thrust_streak": 0,
        "unconfirmed_thrust_streak": 0,
        "thrust_n": 0,
        "confirmed_n": 0,
        "alone_n": 0,
        "confirm_rate_pct": None,
        "density_pct": None,
        "confirmed_density_pct": None,
        "alone_density_pct": None,
        "days_since_thrust": None,
        "days_since_confirmed_thrust": None,
        "days_since_unconfirmed_thrust": None,
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
        "mixed_streak": 0,
        "days_since_risk_on": None,
        "days_since_risk_off": None,
        "days_since_tape_split": None,
        "days_since_mixed": None,
        "days_since_tape_flip": None,
        "flip_streak": 0,
        "flip_max_streak": 0,
        "flip_min_streak": 0,
        "flip_mean_streak": None,
        "flip_median_streak": None,
        "flip_stdev_streak": None,
        "flip_cv_streak": None,
        "flip_run_n": 0,
        "dual_n": 0,
        "split_n": 0,
        "risk_off_n": 0,
        "mixed_n": 0,
        "risk_on_density_pct": None,
        "split_density_pct": None,
        "risk_off_density_pct": None,
        "mixed_density_pct": None,
        "flip_n": 0,
        "pair_n": 0,
        "flip_density_pct": None,
        "crypto_n": 0,
        "stock_n": 0,
        "stock_advance_pct": None,
        "crypto_advance_pct": None,
        "estimate": True,
        "full_universe": False,
        "meta_severity": "",
        "meta_bit": "",
        "run_covers_day": None,
        "meta_scan_day": "",
    }
    if not isinstance(pulse, dict):
        return empty
    meta = build_breadth_day_meta(pulse)
    meta_bit = str(meta.get("bit") or "")
    meta_severity = str(meta.get("severity") or "")
    meta_scan_day = str(meta.get("scan_day") or "")
    run_covers_day = meta.get("run_covers_day")
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
    confirmed = is_confirmed_thrust_day(
        mover_pct, near_pct, advance_pct, crypto_adv_pct
    )
    alone = is_unconfirmed_thrust_day(
        mover_pct, near_pct, advance_pct, crypto_adv_pct
    )
    split = is_tape_split_day(advance_pct, crypto_adv_pct)
    risk_off = is_risk_off_day(advance_pct, crypto_adv_pct)
    tape = breadth_tape_label(advance_pct, crypto_adv_pct)
    mixed = tape == "mixed"
    if crypto_n <= 0 and stock_n <= 0 and breakouts_n <= 0:
        # Zero-priced / mismatch still speak on Overview etc. (parity with
        # Recent days). No day → stay silent (legacy empty pulse).
        if not meta_bit:
            return empty
        coverage = "estimate · not full-universe"
        return {
            **empty,
            "ready": True,
            "tone": "warn",
            "line": f"{meta_bit} · {coverage}",
            "meta_severity": meta_severity,
            "meta_bit": meta_bit,
            "run_covers_day": run_covers_day,
            "meta_scan_day": meta_scan_day,
        }

    crypto_net = crypto_up - crypto_down
    stock_net = stock_up - stock_down
    hist = [r for r in (history or []) if isinstance(r, dict)]
    day = str(pulse.get("day") or "").strip()
    day_cut = day or None
    streak = breadth_thrust_streak(hist, through_day=day_cut) if hist else 0
    confirmed_streak = (
        breadth_confirmed_thrust_streak(hist, through_day=day_cut) if hist else 0
    )
    alone_streak = (
        breadth_unconfirmed_thrust_streak(hist, through_day=day_cut) if hist else 0
    )
    dual_streak = (
        breadth_dual_advance_streak(hist, through_day=day_cut) if hist else 0
    )
    split_streak = (
        breadth_tape_split_streak(hist, through_day=day_cut) if hist else 0
    )
    risk_off_streak = (
        breadth_risk_off_streak(hist, through_day=day_cut) if hist else 0
    )
    mixed_streak = (
        breadth_mixed_streak(hist, through_day=day_cut) if hist else 0
    )
    days_since_thrust = (
        breadth_days_since_thrust(hist, through_day=day_cut) if hist else None
    )
    days_since_confirmed = (
        breadth_days_since_confirmed_thrust(hist, through_day=day_cut)
        if hist
        else None
    )
    days_since_alone = (
        breadth_days_since_unconfirmed_thrust(hist, through_day=day_cut)
        if hist
        else None
    )
    hist_for_rate = hist
    if hist and day_cut:
        cut: list[dict[str, Any]] = []
        for r in hist:
            cut.append(r)
            if str(r.get("day") or "") == day_cut:
                break
        else:
            cut = hist
        hist_for_rate = cut
    rate_sum = (
        build_breadth_thrust_summary(hist_for_rate) if hist_for_rate else {}
    )
    tape_rate_sum = (
        build_breadth_tape_summary(hist_for_rate) if hist_for_rate else {}
    )
    thrust_n = int(rate_sum.get("thrust_n") or 0) if rate_sum else 0
    confirmed_n = int(rate_sum.get("confirmed_n") or 0) if rate_sum else 0
    alone_n = int(rate_sum.get("alone_n") or 0) if rate_sum else 0
    hist_days = int(rate_sum.get("days") or 0) if rate_sum else 0
    confirm_rate = rate_sum.get("confirm_rate_pct") if rate_sum else None
    density = rate_sum.get("density_pct") if rate_sum else None
    conf_density = rate_sum.get("confirmed_density_pct") if rate_sum else None
    alone_density = rate_sum.get("alone_density_pct") if rate_sum else None
    dual_n = int(tape_rate_sum.get("dual_n") or 0) if tape_rate_sum else 0
    split_n = int(tape_rate_sum.get("split_n") or 0) if tape_rate_sum else 0
    risk_off_n = int(tape_rate_sum.get("risk_off_n") or 0) if tape_rate_sum else 0
    mixed_n = int(tape_rate_sum.get("mixed_n") or 0) if tape_rate_sum else 0
    tape_days = int(tape_rate_sum.get("days") or 0) if tape_rate_sum else 0
    risk_on_density = (
        tape_rate_sum.get("risk_on_density_pct") if tape_rate_sum else None
    )
    split_density = (
        tape_rate_sum.get("split_density_pct") if tape_rate_sum else None
    )
    risk_off_density = (
        tape_rate_sum.get("risk_off_density_pct") if tape_rate_sum else None
    )
    mixed_density = (
        tape_rate_sum.get("mixed_density_pct") if tape_rate_sum else None
    )
    flip_n = int(tape_rate_sum.get("flip_n") or 0) if tape_rate_sum else 0
    pair_n = int(tape_rate_sum.get("pair_n") or 0) if tape_rate_sum else 0
    flip_density = (
        tape_rate_sum.get("flip_density_pct") if tape_rate_sum else None
    )
    if confirm_rate is not None:
        try:
            confirm_rate = float(confirm_rate)
        except (TypeError, ValueError):
            confirm_rate = thrust_confirm_rate_pct(confirmed_n, thrust_n)
    if density is not None:
        try:
            density = float(density)
        except (TypeError, ValueError):
            density = thrust_density_pct(thrust_n, hist_days)
    elif rate_sum:
        density = thrust_density_pct(thrust_n, hist_days)
    if conf_density is not None:
        try:
            conf_density = float(conf_density)
        except (TypeError, ValueError):
            conf_density = confirmed_density_pct(confirmed_n, hist_days)
    elif rate_sum:
        conf_density = confirmed_density_pct(confirmed_n, hist_days)
    if alone_density is not None:
        try:
            alone_density = float(alone_density)
        except (TypeError, ValueError):
            alone_density = alone_density_pct(alone_n, hist_days)
    elif rate_sum:
        alone_density = alone_density_pct(alone_n, hist_days)
    dens_days = tape_days or hist_days
    if risk_on_density is not None:
        try:
            risk_on_density = float(risk_on_density)
        except (TypeError, ValueError):
            risk_on_density = tape_label_density_pct(dual_n, dens_days)
    elif tape_rate_sum:
        risk_on_density = tape_label_density_pct(dual_n, dens_days)
    if split_density is not None:
        try:
            split_density = float(split_density)
        except (TypeError, ValueError):
            split_density = tape_label_density_pct(split_n, dens_days)
    elif tape_rate_sum:
        split_density = tape_label_density_pct(split_n, dens_days)
    if risk_off_density is not None:
        try:
            risk_off_density = float(risk_off_density)
        except (TypeError, ValueError):
            risk_off_density = tape_label_density_pct(risk_off_n, dens_days)
    elif tape_rate_sum:
        risk_off_density = tape_label_density_pct(risk_off_n, dens_days)
    if mixed_density is not None:
        try:
            mixed_density = float(mixed_density)
        except (TypeError, ValueError):
            mixed_density = tape_label_density_pct(mixed_n, dens_days)
    elif tape_rate_sum:
        mixed_density = tape_label_density_pct(mixed_n, dens_days)
    if flip_density is not None:
        try:
            flip_density = float(flip_density)
        except (TypeError, ValueError):
            flip_density = tape_flip_density_pct(flip_n, pair_n)
    elif tape_rate_sum:
        flip_density = tape_flip_density_pct(flip_n, pair_n)
    days_since_risk_on = (
        breadth_days_since_risk_on(hist, through_day=day_cut) if hist else None
    )
    days_since_risk_off = (
        breadth_days_since_risk_off(hist, through_day=day_cut) if hist else None
    )
    days_since_tape_split = (
        breadth_days_since_tape_split(hist, through_day=day_cut) if hist else None
    )
    days_since_mixed = (
        breadth_days_since_mixed(hist, through_day=day_cut) if hist else None
    )
    days_since_tape_flip = (
        breadth_days_since_tape_flip(hist, through_day=day_cut) if hist else None
    )
    flip_streak = (
        breadth_tape_flip_streak(hist, through_day=day_cut) if hist else 0
    )
    flip_max_streak = (
        breadth_tape_flip_max_streak(hist, through_day=day_cut) if hist else 0
    )
    flip_mean_streak = (
        breadth_tape_flip_mean_streak(hist, through_day=day_cut) if hist else None
    )
    flip_median_streak = (
        breadth_tape_flip_median_streak(hist, through_day=day_cut) if hist else None
    )
    flip_min_streak = (
        breadth_tape_flip_min_streak(hist, through_day=day_cut) if hist else 0
    )
    flip_stdev_streak = (
        breadth_tape_flip_stdev_streak(hist, through_day=day_cut) if hist else None
    )
    flip_cv_streak = (
        breadth_tape_flip_cv_streak(hist, through_day=day_cut) if hist else None
    )
    flip_run_n = (
        breadth_tape_flip_run_count(hist, through_day=day_cut) if hist else 0
    )
    prev_tape = (
        breadth_prev_tape_label(hist, through_day=day_cut) if hist else ""
    )
    flip = is_tape_flip(prev_tape, tape)
    parts: list[str] = []
    score = 0
    # Meta warn first so truncation keeps coverage + leaves the honesty bit.
    if meta_bit:
        parts.append(meta_bit)
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
    if confirmed and confirmed_streak >= 2:
        parts.append(f"confirmed thrust · streak {confirmed_streak}")
    elif confirmed:
        parts.append("confirmed thrust")
    elif alone and alone_streak >= 2:
        parts.append(f"thrust alone · streak {alone_streak}")
    elif alone or thrust:
        parts.append("thrust alone")
    elif days_since_confirmed is not None and days_since_confirmed > 0:
        parts.append(f"{days_since_confirmed}d since confirmed")
    elif days_since_alone is not None and days_since_alone > 0:
        parts.append(f"{days_since_alone}d since alone")
    elif days_since_thrust is not None and days_since_thrust > 0:
        parts.append(f"{days_since_thrust}d since thrust")
    if dual and dual_streak >= 2:
        parts.append(f"risk-on · streak {dual_streak}")
    elif split and split_streak >= 2:
        parts.append(f"split · streak {split_streak}")
    elif risk_off and risk_off_streak >= 2:
        parts.append(f"risk-off · streak {risk_off_streak}")
    elif mixed and mixed_streak >= 2:
        parts.append(f"mixed · streak {mixed_streak}")
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
    if (
        not split
        and days_since_tape_split is not None
        and days_since_tape_split > 0
    ):
        parts.append(f"{days_since_tape_split}d since split")
    if (
        not mixed
        and days_since_mixed is not None
        and days_since_mixed > 0
    ):
        parts.append(f"{days_since_mixed}d since mixed")
    if flip:
        parts.append(f"flipped {prev_tape}→{tape}")
        if flip_streak >= 2:
            parts.append(f"flip streak {flip_streak}")
    elif (
        days_since_tape_flip is not None
        and days_since_tape_flip > 0
    ):
        parts.append(f"{days_since_tape_flip}d since flip")
    # Flip-run distribution (max/avg/med/min/σ/CV) stays on Breadth chop details.
    # StockBee confirm/density last (before coverage) so days-since stay visible.
    if confirm_rate is not None and thrust_n > 0:
        parts.append(f"confirm {confirm_rate:.0f}% ({confirmed_n}/{thrust_n})")
    if density is not None and hist_days > 0:
        parts.append(f"density {density:.0f}% ({thrust_n}/{hist_days})")
    if conf_density is not None and hist_days > 0:
        parts.append(f"conf dens {conf_density:.0f}% ({confirmed_n}/{hist_days})")
    if alone_density is not None and hist_days > 0:
        parts.append(f"alone dens {alone_density:.0f}% ({alone_n}/{hist_days})")
    if dens_days > 0:
        if risk_on_density is not None:
            parts.append(
                f"risk-on dens {risk_on_density:.0f}% ({dual_n}/{dens_days})"
            )
        if split_density is not None:
            parts.append(
                f"split dens {split_density:.0f}% ({split_n}/{dens_days})"
            )
        if risk_off_density is not None:
            parts.append(
                f"risk-off dens {risk_off_density:.0f}% ({risk_off_n}/{dens_days})"
            )
        if mixed_density is not None:
            parts.append(
                f"mixed dens {mixed_density:.0f}% ({mixed_n}/{dens_days})"
            )
        if flip_density is not None and pair_n > 0:
            parts.append(f"flip dens {flip_density:.0f}% ({flip_n}/{pair_n})")
    if not parts:
        return empty
    # Coverage honesty: verified *scan-list* estimate, never full-universe.
    # Keep this suffix when truncating — days-since / streaks can push length.
    coverage = "estimate · not full-universe"
    core = " · ".join(parts)
    line = f"{core} · {coverage}"
    # StockBee days-since / tape bits grow the line; keep coverage when trimming.
    max_len = 280
    if len(line) > max_len:
        keep = f"… · {coverage}"
        budget = max_len - len(keep)
        if budget < 12:
            line = coverage if len(coverage) <= max_len else coverage[: max_len - 1] + "…"
        else:
            line = core[:budget].rstrip(" ·") + keep
    if meta.get("tone") == "warn":
        tone = "warn"
    elif score > 0:
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
        "is_confirmed_thrust": confirmed,
        "is_unconfirmed_thrust": alone,
        "thrust_streak": streak,
        "confirmed_thrust_streak": confirmed_streak,
        "unconfirmed_thrust_streak": alone_streak,
        "thrust_n": thrust_n,
        "confirmed_n": confirmed_n,
        "alone_n": alone_n,
        "confirm_rate_pct": confirm_rate,
        "density_pct": density,
        "confirmed_density_pct": conf_density,
        "alone_density_pct": alone_density,
        "days_since_thrust": days_since_thrust,
        "days_since_confirmed_thrust": days_since_confirmed,
        "days_since_unconfirmed_thrust": days_since_alone,
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
        "mixed_streak": mixed_streak,
        "days_since_risk_on": days_since_risk_on,
        "days_since_risk_off": days_since_risk_off,
        "days_since_tape_split": days_since_tape_split,
        "days_since_mixed": days_since_mixed,
        "days_since_tape_flip": days_since_tape_flip,
        "flip_streak": flip_streak,
        "flip_max_streak": flip_max_streak,
        "flip_min_streak": flip_min_streak,
        "flip_mean_streak": flip_mean_streak,
        "flip_median_streak": flip_median_streak,
        "flip_stdev_streak": flip_stdev_streak,
        "flip_cv_streak": flip_cv_streak,
        "flip_run_n": flip_run_n,
        "dual_n": dual_n,
        "split_n": split_n,
        "risk_off_n": risk_off_n,
        "mixed_n": mixed_n,
        "risk_on_density_pct": risk_on_density,
        "split_density_pct": split_density,
        "risk_off_density_pct": risk_off_density,
        "mixed_density_pct": mixed_density,
        "flip_n": flip_n,
        "pair_n": pair_n,
        "flip_density_pct": flip_density,
        "crypto_n": crypto_n,
        "stock_n": stock_n if stock_n > 0 else 0,
        "stock_advance_pct": advance_pct if stock_n > 0 else None,
        "crypto_advance_pct": crypto_adv_pct if crypto_n > 0 else None,
        "estimate": True,
        "full_universe": False,
        "meta_severity": meta_severity,
        "meta_bit": meta_bit,
        "run_covers_day": run_covers_day,
        "meta_scan_day": meta_scan_day,
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
        "is_confirmed_thrust": is_confirmed_thrust_day(
            crypto_mover_pct,
            near_high_pct,
            stock_advance_pct,
            crypto_advance_pct,
        ),
        "is_unconfirmed_thrust": is_unconfirmed_thrust_day(
            crypto_mover_pct,
            near_high_pct,
            stock_advance_pct,
            crypto_advance_pct,
        ),
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
            "from": "tradermonty/claude-trading-skills (trader memory + #437 expired) + xang1234/RyanJHamby fresh·aging·expired triad + portfolio AI speak-both-sides + concentration lead",
            "note": "One-line fail-open soft-allow count beside pretrade / risk; hot|aging|cool severity; lead gate when one gate dominates the severity band (≥2, ties silent) speaks rs leads · fresh|aging|expired · ×N with share · ahead · vs runner-up · share Δ wide|thin (mid silent) · share vs Δ clash|align (count-ahead lean ≠ ownership-Δ lean); Ops list tags lead rows as leads · band (same band identity; ≠ row aging/expired); aging (>12h) + expired (>24h) counts + gate tallies consolidated — Ops keeps the full list; display only.",
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

    from stock_checker.ai_validate_memory import (
        latest_ai_actions,
        latest_ai_confidences,
        latest_ai_gated,
        recent_ai_debates,
    )
    from stock_checker.gate_audit import (
        enrich_soft_allows,
        mark_soft_allow_lead_rows,
        recent_soft_allows,
    )
    from stock_checker.risk_halts import (
        book_risk_report,
        latest_stop_loss_sell,
        pretrade_status,
        realized_pnl_for_utc_day,
        suggest_entry_notional,
    )

    soft_allows = enrich_soft_allows(recent_soft_allows(data_dir, limit=12))
    soft_allow_glance = build_soft_allow_glance(soft_allows)
    soft_allows = mark_soft_allow_lead_rows(
        soft_allows,
        lead_gate=str(soft_allow_glance.get("lead_gate") or ""),
        lead_band=str(soft_allow_glance.get("lead_band") or ""),
        runner_gate=str(soft_allow_glance.get("lead_runner_gate") or ""),
    )
    ai_debates = recent_ai_debates(data_dir, limit=8)
    ai_actions = latest_ai_actions(data_dir)
    ai_confidences = latest_ai_confidences(data_dir)
    ai_gated = latest_ai_gated(data_dir)

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
    scan_scores: dict[str, float] = {}
    scan_pct_from_high: dict[str, float] = {}
    scan_change_24h: dict[str, float] = {}
    scan_has_vol: dict[str, bool] = {}
    from stock_checker.atr_risk import risk_note_has_vol

    for key in ("recommendations", "crypto_leaders", "stock_breakouts"):
        for item in opportunities.get(key) or []:
            if not isinstance(item, dict):
                continue
            sym = str(item.get("symbol") or "").strip().upper()
            if not sym:
                continue
            try:
                sc = float(item.get("score"))
            except (TypeError, ValueError):
                sc = None
            if sc is not None:
                prev = scan_scores.get(sym)
                if prev is None or sc > prev:
                    scan_scores[sym] = sc
            try:
                pfh = float(item.get("pct_from_high"))
            except (TypeError, ValueError):
                pfh = None
            if pfh is not None:
                prev_h = scan_pct_from_high.get(sym)
                # Prefer closest-to-high when symbol appears on multiple lists.
                if prev_h is None or pfh > prev_h:
                    scan_pct_from_high[sym] = pfh
            chg: float | None = None
            for chg_key in ("change_24h", "daily_change_pct", "change_pct", "change"):
                if chg_key not in item or item.get(chg_key) is None:
                    continue
                try:
                    chg = float(item[chg_key])
                except (TypeError, ValueError):
                    continue
                break
            if chg is not None:
                prev_c = scan_change_24h.get(sym)
                # Prefer largest |day move| across lists (StockBee heat).
                if prev_c is None or abs(chg) > abs(prev_c):
                    scan_change_24h[sym] = chg
            note = item.get("risk_note")
            if note is None and item.get("summary") is not None:
                note = item.get("summary")
            # Only map symbols that carry a risk_note/summary field.
            if "risk_note" in item or "summary" in item:
                has_vol = risk_note_has_vol(
                    str(note) if note is not None else ""
                )
                # Prefer has-vol when the name appears on multiple lists.
                if sym not in scan_has_vol or has_vol:
                    scan_has_vol[sym] = has_vol
    book_risk = book_risk_report(
        cash=cash,
        equity=equity,
        holdings=rows,
        max_positions=max_pos,
        min_hold_seconds=min_hold_s,
        scan_symbols=(
            str(item.get("symbol"))
            for key in ("recommendations", "crypto_leaders", "stock_breakouts")
            for item in (opportunities.get(key) or [])
            if isinstance(item, dict) and item.get("symbol")
        ),
        scan_leaders=(
            str(item.get("symbol"))
            for item in (opportunities.get("crypto_leaders") or [])
            if isinstance(item, dict) and item.get("symbol")
        ),
        scan_breakouts=(
            str(item.get("symbol"))
            for item in (opportunities.get("stock_breakouts") or [])
            if isinstance(item, dict) and item.get("symbol")
        ),
        scan_recommendations=(
            str(item.get("symbol"))
            for item in (opportunities.get("recommendations") or [])
            if isinstance(item, dict) and item.get("symbol")
        ),
        scan_scores=scan_scores,
        scan_pct_from_high=scan_pct_from_high,
        scan_change_24h=scan_change_24h,
        scan_has_vol=scan_has_vol,
        ai_actions=ai_actions,
        ai_confidences=ai_confidences,
        ai_gated=ai_gated,
        trades=trades,
    )
    runtime = _trader_runtime_view()
    scan_interval_sec = max(60, int(runtime.get("scan_interval_min") or 15) * 60)
    scan_time_raw = opportunities.get("scan_time") or ""
    mark_coverage = build_mark_coverage(rows)
    ledger_health = build_ledger_health(data_dir)
    mark_base = {
        "live": "Marks from live quotes + latest scan.",
        "live+scan": "Marks from live quotes + latest scan.",
        "scan": "Marks from latest scan prices (live quotes skipped/unavailable).",
        "cost": "Showing cost basis — no fresh marks yet.",
    }.get(mark_source, "")
    cov_bit = str(mark_coverage.get("bit") or "")
    mark_note = f"{mark_base} {cov_bit}." if mark_base and cov_bit else mark_base

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
        "soft_allow_glance": soft_allow_glance,
        "entry_gates_glance": build_entry_gates_glance(runtime),
        "calm_streak_glance": build_calm_streak_glance(runtime),
        "promote_ab_glance": build_promote_ab_glance(
            {**runtime, "max_positions": max_pos, "open_positions": len(rows)},
            data_dir=data_dir,
            open_positions=len(rows),
        ),
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
        "atr_display_glance": build_atr_display_glance(
            list(crypto_leaders) + list(stock_breakouts) + list(recs)
        ),
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
        "mark_coverage": mark_coverage,
        "ledger_health": ledger_health,
        "mark_note": mark_note,
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
