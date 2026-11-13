"""Chart series for the paper desk (equity, allocation, price history)."""

from __future__ import annotations

import json
import math
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from openbb_backend.symbol_names import display_name, resolve_symbol_names

# xang1234 #498: chart cache basenames stay under chart_bars/ (no path escape).
_CHART_CACHE_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._=-]{0,63}$")


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return default
    return n if math.isfinite(n) else default


def _load_json(path: Path, default: Any) -> Any:
    """Parse JSON via desk lean-checked loader (xang1234 #498 / #540)."""
    from openbb_backend.desk import load_json_checked

    doc, _meta = load_json_checked(path, default)
    return doc


def _load_opportunities(data_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Prefer opportunities_latest; fall back like desk (xang1234 #682/#685).

    Charts used to hard-read ``opportunities_latest.json`` only — a missing,
    dangling, or stale pin hid the newest publish that desk already falls
    back to. Returns ``(opportunities, archive_res)``.
    """
    from openbb_backend.desk import resolve_opportunities_archive

    archive_res = resolve_opportunities_archive(data_dir)
    opp = _load_json(Path(archive_res["path"]), {})
    if not isinstance(opp, dict):
        opp = {}
    return opp, archive_res


def _parse_chart_points(raw: Any) -> list[dict[str, Any]]:
    """Parse advertised chart points — presence alone is not enough.

    xang1234 c6f8650: require a list of point objects with finite closes;
    skip non-dicts and junk closes rather than treating a truthy blob as hit.
    """
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for p in raw:
        if not isinstance(p, dict):
            continue
        close = _finite(p.get("close"), default=float("nan"))
        if not math.isfinite(close):
            continue
        out.append({"t": p.get("t"), "close": round(close, 6)})
    return out


def _load_jsonl(path: Path) -> list[dict]:
    from openbb_backend.desk import load_jsonl_checked

    rows, _meta = load_jsonl_checked(path)
    return rows


def _parse_trade_ts(raw: str) -> Optional[datetime]:
    raw = (raw or "").strip()
    if not raw:
        return None
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(raw[:26], fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(
            timezone.utc
        )
    except ValueError:
        return None


def build_equity_curve(data_dir: Path) -> list[dict[str, Any]]:
    """Book equity after each fill (cash + cost basis of open lots)."""
    portfolio = _load_json(data_dir / "portfolio.json", {})
    trades = _load_jsonl(data_dir / "trades.jsonl")
    initial = float(portfolio.get("initial_cash") or 0)
    cash = initial
    lots: dict[str, dict[str, float]] = {}  # symbol -> {qty, cost}
    points: list[dict[str, Any]] = []

    start_ts = None
    if trades:
        start_ts = _parse_trade_ts(str(trades[0].get("timestamp") or ""))
    if start_ts is None and portfolio.get("last_updated"):
        start_ts = _parse_trade_ts(str(portfolio["last_updated"]))
    if start_ts is None:
        start_ts = datetime.now(timezone.utc)

    points.append(
        {
            "t": start_ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "equity": round(initial, 2),
            "cash": round(initial, 2),
            "invested": 0.0,
            "label": "start",
        }
    )

    for trade in trades:
        side = str(trade.get("type") or "").upper()
        sym = str(trade.get("symbol") or "")
        qty = float(trade.get("quantity") or 0)
        price = float(trade.get("price") or 0)
        commission = float(trade.get("commission") or 0)
        ts = _parse_trade_ts(str(trade.get("timestamp") or "")) or start_ts

        if side == "BUY":
            total = qty * price + commission
            cash -= total
            lot = lots.setdefault(sym, {"qty": 0.0, "cost": 0.0})
            lot["qty"] += qty
            lot["cost"] += qty * price
            if trade.get("cash_remaining") is not None:
                cash = float(trade["cash_remaining"])
        elif side == "SELL":
            lot = lots.setdefault(sym, {"qty": 0.0, "cost": 0.0})
            avg = (lot["cost"] / lot["qty"]) if lot["qty"] else price
            proceeds = qty * price - commission
            cash += proceeds
            lot["qty"] = max(0.0, lot["qty"] - qty)
            lot["cost"] = max(0.0, lot["qty"] * avg)
            if lot["qty"] <= 1e-12:
                lots.pop(sym, None)
            if trade.get("cash_remaining") is not None:
                cash = float(trade["cash_remaining"])

        invested = sum(v["cost"] for v in lots.values())
        # Prefer live portfolio cash if this is the last trade
        equity = cash + invested
        points.append(
            {
                "t": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "equity": round(equity, 2),
                "cash": round(cash, 2),
                "invested": round(invested, 2),
                "label": f"{side} {sym}".strip(),
            }
        )

    # Anchor current book mark if available
    holdings = portfolio.get("holdings") or {}
    avg = portfolio.get("avg_buy_price") or {}
    if holdings:
        cash_now = float(portfolio.get("cash") or cash)
        invested_now = sum(
            float(q) * float(avg.get(s, 0) or 0) for s, q in holdings.items()
        )
        points.append(
            {
                "t": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "equity": round(cash_now + invested_now, 2),
                "cash": round(cash_now, 2),
                "invested": round(invested_now, 2),
                "label": "now",
            }
        )
    return points


def build_allocation(data_dir: Path) -> list[dict[str, Any]]:
    from openbb_backend.desk import load_desk_snapshot

    # Cost/scan marks only — keep chart payload snappy.
    snap = load_desk_snapshot(
        data_dir,
        live_marks=False,
        price_fetcher=lambda _s: {},
    )
    # Prefer MTM weights from snapshot holdings
    rows = []
    for h in snap.get("holdings") or []:
        rows.append(
            {
                "symbol": h["symbol"],
                "name": h.get("name") or "",
                "value": round(float(h.get("market_value") or 0), 2),
                "weight_pct": round(float(h.get("weight_pct") or 0), 2),
                "kind": h.get("kind") or "stock",
            }
        )
    cash = float(snap.get("cash") or 0)
    equity = float(snap.get("equity") or 0) or 1.0
    rows.append(
        {
            "symbol": "CASH",
            "name": "Cash",
            "value": round(cash, 2),
            "weight_pct": round(cash / equity * 100, 2),
            "kind": "cash",
        }
    )
    rows.sort(key=lambda r: r["value"], reverse=True)
    return rows


def _safe_chart_cache_token(raw: str) -> str | None:
    """Basename token for chart_bars — reject empty / escape / junk.

    xang1234 #498 advertised-path containment: slash→underscore keeps
    BTC/USDT-style names; ``..`` and other path junk stay out.
    """
    text = str(raw or "").strip().replace("/", "_").replace("\\", "_")
    if not text or ".." in text or not _CHART_CACHE_TOKEN.match(text):
        return None
    return text


def _cache_path(
    data_dir: Path, symbol: str, interval: str = "1d"
) -> Path | None:
    """Resolve a chart cache file under ``chart_bars/`` or None if unsafe.

    xang1234 #498 / 464a0ce: resolved path must stay inside the chart root
    (``is_relative_to``); empty/malformed tokens refuse the cache slot.
    """
    safe = _safe_chart_cache_token(symbol)
    if safe is None:
        return None
    root = (Path(data_dir) / "chart_bars").resolve()
    if interval in {"1d", "d", "day", "daily"}:
        name = f"{safe}.json"
    else:
        safe_iv = _safe_chart_cache_token(interval)
        if safe_iv is None:
            return None
        name = f"{safe}_{safe_iv}.json"
    try:
        path = (root / name).resolve()
    except (OSError, ValueError):
        return None
    if not path.is_relative_to(root):
        return None
    return path


def _yf_period_for(days: int, interval: str) -> str:
    """yfinance period hints by bar size (intraday windows are short)."""
    if interval in {"15m", "5m", "2m", "1m"}:
        return "5d" if days <= 5 else "7d"
    if interval in {"60m", "1h", "90m"}:
        if days <= 7:
            return "7d"
        if days <= 30:
            return "1mo"
        return "3mo"
    return "3mo" if days <= 100 else "6mo"


def hold_chart_interval(span_hours: float, *, is_crypto: bool = False) -> str:
    """
    Pick bar size so short holds (esp. weekend crypto) are not a 2-point line.

    Daily bars often have zero points between a morning fill and “now”.
    """
    if span_hours <= 36:
        return "15m"
    if span_hours <= 72 or (is_crypto and span_hours <= 14 * 24):
        return "1h"
    return "1d"


# Daily chart last-bar age (display only). Same bands as desk cash_print:
# fresh <12h · aging <36h · else stale (weekend / missed session).
# tradermonty #675 rejects stale daily bars before scoring — we speak only.
CHART_BAR_FRESH_HOURS = 12
CHART_BAR_AGING_HOURS = 36
# Book-level aging|stale ownership of relative-price panels (display only).
# Same hot/quiet bands as Screener junk share / Yahoo claim-drop share.
CHART_BARS_SPOKEN_SHARE_HOT = 50.0
CHART_BARS_SPOKEN_SHARE_QUIET = 25.0
# Remaining fresh after spoken share (display only) — Screener ok / claim
# vs-kept bands: strong ≥75% · thin <50%.
CHART_BARS_FRESH_SHARE_STRONG = 75.0
CHART_BARS_FRESH_SHARE_THIN = 50.0


def chart_price_bars_vs_fresh(
    n_spoken: int,
    n_fresh: int,
    n_panels: int,
) -> tuple[str, int | None, float | None, str]:
    """Remaining fresh panels when spoken share already spoke (display only).

    Spoken% alone hid usable fresh peers (Screener junk vs ok / Yahoo
    claim-drop vs kept + portfolio AI speak-both-sides). Returns
    ``(bit, fresh_n, fresh_pct, severity)``. Zero spoken → silent.
    All-spoken → ``vs 0 fresh · thin · 0%``. ``strong`` ≥75% · ``thin``
    <50% · mid shows the percent only.
    """
    try:
        spoken = max(0, int(n_spoken))
    except (TypeError, ValueError):
        spoken = 0
    try:
        fresh = max(0, int(n_fresh))
    except (TypeError, ValueError):
        fresh = 0
    try:
        panels = max(0, int(n_panels))
    except (TypeError, ValueError):
        panels = 0
    if spoken <= 0 or panels <= 0:
        return "", None, None, ""
    fresh = min(fresh, panels)
    fresh_pct = round(100.0 * fresh / panels, 1)
    if fresh_pct >= CHART_BARS_FRESH_SHARE_STRONG:
        severity = "strong"
        sev_bit = f"strong · {fresh_pct:g}%"
    elif fresh_pct < CHART_BARS_FRESH_SHARE_THIN:
        severity = "thin"
        sev_bit = f"thin · {fresh_pct:g}%"
    else:
        severity = ""
        sev_bit = f"{fresh_pct:g}%"
    return f"vs {fresh} fresh · {sev_bit}", fresh, fresh_pct, severity


def chart_price_bars_spoken_vs_fresh_lead(
    n_spoken: int,
    n_fresh: int,
) -> tuple[str, str, int | None]:
    """Strict lead among spoken vs fresh panel counts (display only).

    Absolute ``N bars aging|stale`` beside ``vs M fresh`` hid which slot
    owns the book (opportunity damaged vs ok lead / Yahoo claim-drop vs
    live + portfolio AI count≠share + xang1234 multi-meter). Both sides
    must be >0 and total ≥2; strict lead → ``lead spoken · N%`` /
    ``lead fresh · N%``; ties / sole-side → silent (use
    ``chart_price_bars_spoken_vs_fresh_sample_gap`` for ``spoken/fresh tied``).
    """
    try:
        spoken = max(0, int(n_spoken))
    except (TypeError, ValueError):
        spoken = 0
    try:
        fresh = max(0, int(n_fresh))
    except (TypeError, ValueError):
        fresh = 0
    total = spoken + fresh
    if total < 2 or spoken <= 0 or fresh <= 0 or spoken == fresh:
        return "", "", None
    if spoken > fresh:
        name, n = "spoken", spoken
    else:
        name, n = "fresh", fresh
    share = int(round(100.0 * n / total))
    return f"lead {name} · {share}%", name, share


def chart_price_bars_spoken_vs_fresh_sample_gap(
    n_spoken: int,
    n_fresh: int,
) -> str:
    """Speak ``spoken/fresh tied`` when both sides spoke with no strict lead.

    Prefixed so the bit stays distinct from ``aging/stale tied``. Lead /
    sole-side / zero stay silent. Display only.
    """
    try:
        spoken = max(0, int(n_spoken))
    except (TypeError, ValueError):
        spoken = 0
    try:
        fresh = max(0, int(n_fresh))
    except (TypeError, ValueError):
        fresh = 0
    if spoken <= 0 or fresh <= 0:
        return ""
    lead_bit, _name, _share = chart_price_bars_spoken_vs_fresh_lead(
        spoken, fresh
    )
    if lead_bit:
        return ""
    return "spoken/fresh tied"


def chart_last_bar_meta(
    points: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Last daily close age band for chart honesty (display only).

    Scan/Yahoo cache age ≠ whether the plotted close is a completed session.
    Missing/unparseable stamps stay silent.
    """
    empty: dict[str, Any] = {
        "last_bar": "",
        "bar_age_sec": None,
        "bar_freshness": "",
        "bar_age_label": "",
    }
    if not points:
        return empty
    ts = _parse_trade_ts(str(points[-1].get("t") or ""))
    if ts is None:
        return empty
    clock = now or datetime.now(timezone.utc)
    age = max(0.0, (clock - ts).total_seconds())
    if age < CHART_BAR_FRESH_HOURS * 3600:
        band = "fresh"
    elif age < CHART_BAR_AGING_HOURS * 3600:
        band = "aging"
    else:
        band = "stale"
    if age < 3600:
        label = f"{int(age // 60)}m ago"
    elif age < 36 * 3600:
        label = f"{int(age // 3600)}h ago"
    else:
        label = f"{int(age // 86400)}d ago"
    return {
        "last_bar": ts.strftime("%Y-%m-%d"),
        "bar_age_sec": int(age),
        "bar_freshness": band,
        "bar_age_label": label,
    }


def chart_price_bars_aging_stale_lead(
    n_aging: int,
    n_stale: int,
) -> tuple[str, str, int | None]:
    """Strict lead among aging vs stale spoken bars (display only).

    Absolute ``N aging · M stale`` hid which band owns the spoken set
    (Yahoo claim-drop dead/stale lead + portfolio AI count≠share +
    xang1234 multi-meter). Both sides must be >0 and total ≥2; strict lead
    → ``lead stale · N%`` / ``lead aging · N%``; ties / sole-side → silent
    (use ``chart_price_bars_aging_stale_sample_gap`` for ``aging/stale tied``).
    """
    try:
        aging = max(0, int(n_aging))
    except (TypeError, ValueError):
        aging = 0
    try:
        stale = max(0, int(n_stale))
    except (TypeError, ValueError):
        stale = 0
    total = aging + stale
    if total < 2 or aging <= 0 or stale <= 0 or aging == stale:
        return "", "", None
    if stale > aging:
        name, n = "stale", stale
    else:
        name, n = "aging", aging
    share = int(round(100.0 * n / total))
    return f"lead {name} · {share}%", name, share


def chart_price_bars_aging_stale_sample_gap(
    n_aging: int,
    n_stale: int,
) -> str:
    """Speak ``aging/stale tied`` when both bands spoke with no strict lead.

    Prefixed so the bit stays distinct from other glance ``tied`` chips.
    Lead / sole-side / zero stay silent. Display only.
    """
    try:
        aging = max(0, int(n_aging))
    except (TypeError, ValueError):
        aging = 0
    try:
        stale = max(0, int(n_stale))
    except (TypeError, ValueError):
        stale = 0
    if aging <= 0 or stale <= 0:
        return ""
    lead_bit, _name, _share = chart_price_bars_aging_stale_lead(aging, stale)
    if lead_bit:
        return ""
    return "aging/stale tied"


def chart_price_bars_aging_stale_lead_size(
    n_aging: int,
    n_stale: int,
    *,
    lead_name: str = "",
) -> tuple[float | None, int | None, int | None]:
    """How many times louder owns quieter after aging/stale lead (display only).

    When ``lead_name`` already spoke (``aging|stale``) and both counts are
    >0, ``lead size · N×`` is louder÷quieter; zero quieter stays silent.
    Desk names sides ``aging|stale N · stale|aging M`` (louder first;
    anonymous louder/quieter dropped — Mode A / Screener / opportunity
    named-sides parity). Lead name/% ≠ magnitude (opportunity / Screener
    Δ lead size + portfolio AI count≠share). Returns
    ``(size, louder_n, quieter_n)`` or all-None.
    """
    if str(lead_name or "").strip().casefold() not in {"aging", "stale"}:
        return None, None, None
    try:
        aging = max(0, int(n_aging))
    except (TypeError, ValueError):
        aging = 0
    try:
        stale = max(0, int(n_stale))
    except (TypeError, ValueError):
        stale = 0
    quieter = min(aging, stale)
    louder = max(aging, stale)
    if quieter <= 0:
        return None, None, None
    return round(louder / quieter, 2), louder, quieter


# Quiet price-bars lean chip names spoken stages (Screener / pin lean inventory).
# Longer prefixes first so ``lead size sides`` ≠ ``lead size`` / ``lead stale``.
_PRICE_BARS_LEAN_NAME_CAP = 4
_PRICE_BARS_LEAN_STAGE_RES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^vs \d+ fresh\b"), "vs fresh"),
    (re.compile(r"^spoken/fresh tied\b"), "sf tied"),
    (re.compile(r"^lead spoken\b"), "spoken"),
    (re.compile(r"^lead fresh\b"), "fresh lead"),
    (re.compile(r"^aging/stale tied\b"), "as tied"),
    (re.compile(r"^lead size sides\b"), "sides"),
    (re.compile(r"^lead size\b"), "size"),
    (re.compile(r"^lead stale\b"), "stale"),
    (re.compile(r"^lead aging\b"), "aging"),
)


def chart_price_bars_lean_meta(lean: str, *, warn: bool = False) -> str:
    """Summary chip for Charts price-bars lean fold (display only).

    Quiet names stages that spoke (``quiet · N folds · vs fresh · spoken ·
    size``) so bare ``quiet`` does not claim lead/size when those bits are
    absent — Screener weight / opportunity pin lean meta + MonsterDeveloper
    fold inventory after ownership cascade hid the ladder. Warned folds speak
    ``warn`` and append the clipped stages. Not a gate.
    """
    from stock_checker.yahoo_universe_discovery import _quiet_inventory_chip

    text = str(lean or "").strip()
    if not text:
        return "quiet"
    if warn:
        stage_tail = _quiet_inventory_chip(
            text,
            _PRICE_BARS_LEAN_STAGE_RES,
            cap=_PRICE_BARS_LEAN_NAME_CAP,
            quiet=False,
        )
        if stage_tail:
            return f"warn · {stage_tail}"
        return "warn"
    return _quiet_inventory_chip(
        text, _PRICE_BARS_LEAN_STAGE_RES, cap=_PRICE_BARS_LEAN_NAME_CAP
    )


def chart_price_bars_glance(
    panels: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Book-level last-bar aging|stale after per-legend bits (display only).

    Absolute ``N bars stale`` alone hid one hung panel vs most of the relative
    book — speak ownership share (portfolio AI count≠share + xang1234 multi-meter).
    When spoken share already spoke, also speak ``vs N fresh · [strong|thin] ·
    P%`` so spoken% ≠ silent empty fresh peers (Screener junk vs ok / Yahoo
    claim-drop vs kept). When vs-fresh already spoke and both spoken + fresh
    counts are >0, also speak ``lead spoken|fresh · N%`` or
    ``spoken/fresh tied`` so absolute sides ≠ silent book ownership. When both
    aging and stale spoke, also speak ``lead stale|aging · N%`` or
    ``aging/stale tied`` so absolute sides ≠ silent ownership. After a strict
    aging/stale lead, also speak ``lead size · N×`` + named
    ``lead size sides · aging|stale N · stale|aging M`` (louder first) so
    name/% ≠ magnitude and anonymous louder/quieter does not hide which
    spoken-band sleeve owns quieter. Ownership/lead cascade sits in ``lean``
    under a Charts fold (MonsterDeveloper weight/sleeve lean parity — share
    alone hid vs-fresh / lead / size); ``lean_meta`` names spoken stages.
    Full ``bit`` stays joined for tests. Zero spoken stays silent. Not a
    scoring veto / not a new entry gate.
    """
    empty: dict[str, Any] = {
        "ready": False,
        "bit": "",
        "bit_core": "",
        "line": "",
        "lean": "",
        "lean_warn": False,
        "lean_meta": "quiet",
        "tone": "flat",
        "n_panels": 0,
        "n_fresh": 0,
        "n_aging": 0,
        "n_stale": 0,
        "n_spoken": 0,
        "spoken_share_pct": None,
        "spoken_share_severity": "",
        "vs_fresh": "",
        "vs_fresh_n": None,
        "vs_fresh_share_pct": None,
        "vs_fresh_severity": "",
        "spoken_vs_fresh_lead": "",
        "spoken_vs_fresh_lead_name": "",
        "spoken_vs_fresh_lead_share_pct": None,
        "spoken_vs_fresh_sample_gap": "",
        "aging_stale_lead": "",
        "aging_stale_lead_name": "",
        "aging_stale_lead_share_pct": None,
        "aging_stale_sample_gap": "",
        "aging_stale_lead_size": None,
        "aging_stale_lead_size_louder": None,
        "aging_stale_lead_size_quieter": None,
    }
    if not isinstance(panels, list) or not panels:
        return empty
    n_fresh = n_aging = n_stale = 0
    for p in panels:
        if not isinstance(p, dict):
            continue
        band = str(p.get("bar_freshness") or "")
        if band == "fresh":
            n_fresh += 1
        elif band == "aging":
            n_aging += 1
        elif band == "stale":
            n_stale += 1
    n_panels = n_fresh + n_aging + n_stale
    n_spoken = n_aging + n_stale
    if n_panels <= 0 or n_spoken <= 0:
        return {**empty, "n_panels": n_panels, "n_fresh": n_fresh}
    if n_aging and n_stale:
        count_bit = f"{n_aging} aging · {n_stale} stale"
    elif n_stale:
        count_bit = f"{n_stale} bars stale"
    else:
        count_bit = f"{n_aging} bars aging"
    spoken_share_pct = round(100.0 * n_spoken / n_panels, 1)
    if spoken_share_pct >= CHART_BARS_SPOKEN_SHARE_HOT:
        spoken_share_severity = "hot"
        share_bit = f"hot · {spoken_share_pct:g}%"
    elif spoken_share_pct <= CHART_BARS_SPOKEN_SHARE_QUIET:
        spoken_share_severity = "quiet"
        share_bit = f"quiet · {spoken_share_pct:g}%"
    else:
        spoken_share_severity = ""
        share_bit = f"{spoken_share_pct:g}%"
    vs_fresh_bit, vs_fresh_n, vs_fresh_pct, vs_fresh_sev = (
        chart_price_bars_vs_fresh(n_spoken, n_fresh, n_panels)
    )
    sf_lead_bit, sf_lead_name, sf_lead_share = (
        chart_price_bars_spoken_vs_fresh_lead(n_spoken, n_fresh)
        if vs_fresh_bit
        else ("", "", None)
    )
    sf_sample_gap = (
        chart_price_bars_spoken_vs_fresh_sample_gap(n_spoken, n_fresh)
        if vs_fresh_bit
        else ""
    )
    lead_bit, lead_name, lead_share = chart_price_bars_aging_stale_lead(
        n_aging, n_stale
    )
    sample_gap = chart_price_bars_aging_stale_sample_gap(n_aging, n_stale)
    size, louder_n, quieter_n = chart_price_bars_aging_stale_lead_size(
        n_aging, n_stale, lead_name=lead_name
    )
    own_bit = lead_bit or sample_gap
    sf_own = sf_lead_bit or sf_sample_gap
    bit_core = f"{count_bit} · {share_bit}"
    lean_parts: list[str] = []
    if vs_fresh_bit:
        lean_parts.append(vs_fresh_bit)
    if sf_own:
        lean_parts.append(sf_own)
    if own_bit:
        lean_parts.append(own_bit)
    if size is not None and louder_n is not None and quieter_n is not None:
        other = "stale" if lead_name == "aging" else "aging"
        lean_parts.append(f"lead size · {size:g}×")
        lean_parts.append(
            f"lead size sides · {lead_name} {louder_n} · {other} {quieter_n}"
        )
    lean = " · ".join(lean_parts)
    bit = f"{bit_core} · {lean}" if lean else bit_core
    tone = "flat"
    if n_stale or spoken_share_severity == "hot":
        tone = "warn"
    elif n_aging:
        tone = "aging"
    # Thin fresh remainder escalates warn when share was already hot/aging.
    if vs_fresh_sev == "thin" and tone == "flat":
        tone = "aging"
    lean_warn = tone == "warn"
    return {
        "ready": True,
        "bit": bit,
        "bit_core": bit_core,
        "line": bit_core,
        "lean": lean,
        "lean_warn": lean_warn,
        "lean_meta": chart_price_bars_lean_meta(lean, warn=lean_warn),
        "tone": tone,
        "n_panels": n_panels,
        "n_fresh": n_fresh,
        "n_aging": n_aging,
        "n_stale": n_stale,
        "n_spoken": n_spoken,
        "spoken_share_pct": spoken_share_pct,
        "spoken_share_severity": spoken_share_severity,
        "vs_fresh": vs_fresh_bit,
        "vs_fresh_n": vs_fresh_n,
        "vs_fresh_share_pct": vs_fresh_pct,
        "vs_fresh_severity": vs_fresh_sev,
        "spoken_vs_fresh_lead": sf_lead_bit,
        "spoken_vs_fresh_lead_name": sf_lead_name,
        "spoken_vs_fresh_lead_share_pct": sf_lead_share,
        "spoken_vs_fresh_sample_gap": sf_sample_gap,
        "aging_stale_lead": lead_bit,
        "aging_stale_lead_name": lead_name,
        "aging_stale_lead_share_pct": lead_share,
        "aging_stale_sample_gap": sample_gap,
        "aging_stale_lead_size": size,
        "aging_stale_lead_size_louder": louder_n,
        "aging_stale_lead_size_quieter": quieter_n,
    }


def fetch_price_history(
    symbol: str,
    data_dir: Path,
    *,
    days: int = 90,
    live: bool = True,
    interval: str = "1d",
) -> list[dict[str, Any]]:
    """OHLC closes for symbol; cached under data/chart_bars/ (per interval)."""
    path = _cache_path(data_dir, symbol, interval=interval)
    if path is None:
        # Unsafe token — do not touch disk outside chart_bars (xang1234 #498).
        return []
    cached = _load_json(path, {})
    # Intraday moves faster — shorter cache TTL.
    max_age = 45 * 60 if interval != "1d" else 6 * 3600
    cleaned = _parse_chart_points(cached.get("points"))

    if (
        cached.get("symbol") == symbol
        and cached.get("interval", "1d") == interval
        and cleaned
        and (time.time() - float(cached.get("fetched_at") or 0)) < max_age
    ):
        return cleaned

    if not live:
        return cleaned

    try:
        import yfinance as yf

        period = _yf_period_for(days, interval)
        hist = yf.Ticker(symbol).history(period=period, interval=interval)
        points: list[dict[str, Any]] = []
        if hist is not None and not hist.empty:
            for idx, row in hist.iterrows():
                try:
                    ts = idx.to_pydatetime().astimezone(timezone.utc)
                except Exception:
                    ts = datetime.now(timezone.utc)
                close = _finite(row.get("Close"), default=float("nan"))
                if not math.isfinite(close):
                    continue
                points.append(
                    {
                        "t": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "close": round(close, 6),
                    }
                )
        if points:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "symbol": symbol,
                        "interval": interval,
                        "fetched_at": time.time(),
                        "points": points,
                    }
                )
                + "\n"
            )
        return points
    except Exception:
        return cleaned


def build_price_panels(
    data_dir: Path, *, days: int = 90, live: Optional[bool] = None
) -> list[dict[str, Any]]:
    if live is None:
        live = os.getenv("DESK_CHART_LIVE", "1").strip() not in {
            "0",
            "false",
            "False",
            "no",
        }
    portfolio = _load_json(data_dir / "portfolio.json", {})
    holds_raw = portfolio.get("holdings")
    holdings = list(holds_raw.keys()) if isinstance(holds_raw, dict) else []
    # Also include top scan breakouts for color
    opp, _pin = _load_opportunities(data_dir)
    breakouts = opp.get("stock_breakouts")
    extras: list[str] = []
    if isinstance(breakouts, list):
        for r in breakouts[:4]:
            if isinstance(r, dict) and r.get("symbol"):
                extras.append(str(r["symbol"]))
    symbols: list[str] = []
    for s in holdings + extras:
        if s and s not in symbols:
            symbols.append(str(s))
    symbols = symbols[:8]
    names = resolve_symbol_names(symbols, data_dir, live=False)
    panels = []
    for sym in symbols:
        pts = fetch_price_history(sym, data_dir, days=days, live=live, interval="1d")
        if len(pts) < 2:
            continue
        base = _finite(pts[0]["close"])
        if base <= 0:
            continue
        indexed = []
        for p in pts:
            close = _finite(p["close"], default=float("nan"))
            if not math.isfinite(close):
                continue
            indexed.append(
                {
                    "t": p["t"],
                    "close": close,
                    "rebased": round(close / base * 100, 4),
                }
            )
        if len(indexed) < 2:
            continue
        last = indexed[-1]
        bar_meta = chart_last_bar_meta(indexed)
        panels.append(
            {
                "symbol": sym,
                "name": display_name(sym, names) or sym,
                "points": indexed,
                "last": last["close"],
                "change_pct": round(last["rebased"] - 100, 2),
                **bar_meta,
            }
        )
    return panels


def build_from_buy_panels(
    data_dir: Path, *, days: int = 180, live: Optional[bool] = None
) -> list[dict[str, Any]]:
    """Open lots rebased to avg buy (=100). Honest path since entry — no forecast."""
    if live is None:
        live = os.getenv("DESK_CHART_LIVE", "1").strip() not in {
            "0",
            "false",
            "False",
            "no",
        }
    portfolio = _load_json(data_dir / "portfolio.json", {})
    holdings = portfolio.get("holdings") or {}
    avg = portfolio.get("avg_buy_price") or {}
    entry_times = _load_json(data_dir / "entry_times.json", {})
    opportunities, _pin = _load_opportunities(data_dir)
    from openbb_backend.desk import _prices_from_scan

    marks = _prices_from_scan(opportunities)
    symbols = [str(s) for s in holdings.keys() if s][:10]
    names = resolve_symbol_names(symbols, data_dir, live=False)
    panels: list[dict[str, Any]] = []

    for sym in symbols:
        buy_price = _finite(avg.get(sym))
        qty = _finite(holdings.get(sym))
        if buy_price <= 0 or qty <= 0:
            continue
        entry_raw = entry_times.get(sym)
        entry_ts = _finite(entry_raw) if entry_raw not in (None, "") else 0.0
        buy_dt: Optional[datetime] = None
        if entry_ts > 0:
            buy_dt = datetime.fromtimestamp(entry_ts, tz=timezone.utc)

        now = datetime.now(timezone.utc)
        span_hours_est = (
            max(0.0, (now - buy_dt).total_seconds() / 3600.0) if buy_dt else float(days * 24)
        )
        is_crypto = "-USD" in sym.upper() or sym.upper().endswith("USDT")
        interval = hold_chart_interval(span_hours_est, is_crypto=is_crypto)
        hist_days = max(2, min(days, int(span_hours_est / 24) + 2))
        if interval != "1d":
            hist_days = min(hist_days, 7 if interval == "15m" else 30)

        hist = fetch_price_history(
            sym, data_dir, days=hist_days, live=live, interval=interval
        )
        # Fall back to daily if intraday empty (offline / provider gap).
        if len(hist) < 2 and interval != "1d":
            hist = fetch_price_history(
                sym, data_dir, days=days, live=live, interval="1d"
            )
            interval = "1d"

        pts: list[dict[str, Any]] = []
        for p in hist:
            ts = _parse_trade_ts(str(p.get("t") or ""))
            if ts is None:
                continue
            if buy_dt and ts < buy_dt:
                continue
            close = _finite(p.get("close"), default=float("nan"))
            if not math.isfinite(close) or close <= 0:
                continue
            pts.append({"t": ts.strftime("%Y-%m-%dT%H:%M:%SZ"), "close": close})

        # Always anchor at the fill so short holds still chart.
        buy_iso = (
            buy_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            if buy_dt
            else (pts[0]["t"] if pts else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        )
        if not pts or pts[0]["t"] > buy_iso:
            pts = [{"t": buy_iso, "close": buy_price}] + pts
        elif abs(pts[0]["close"] - buy_price) / buy_price > 0.02:
            # Prefer cost basis as the day-0 mark when history starts mid-hold.
            pts = [{"t": buy_iso, "close": buy_price}] + [
                p for p in pts if p["t"] > buy_iso
            ]

        # Prefer current scan mark as the right edge so short holds aren't a
        # flat cost→cost stub when the book already shows a different last.
        mark = _finite(marks.get(sym))
        now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        if mark > 0:
            pts = [p for p in pts if p["t"] < now_iso]
            pts.append({"t": now_iso, "close": mark})
        elif len(pts) < 2:
            last_close = pts[0]["close"] if pts else buy_price
            if not pts:
                pts = [{"t": buy_iso, "close": buy_price}]
            if pts[-1]["t"] != now_iso:
                pts.append({"t": now_iso, "close": last_close})

        indexed = []
        for p in pts:
            close = _finite(p["close"])
            indexed.append(
                {
                    "t": p["t"],
                    "close": close,
                    "rebased": round(close / buy_price * 100, 4),
                }
            )
        last = indexed[-1]
        first_t = indexed[0]["t"]
        last_t = last["t"]
        span_hours = 0.0
        try:
            t0 = datetime.fromisoformat(first_t.replace("Z", "+00:00"))
            t1 = datetime.fromisoformat(last_t.replace("Z", "+00:00"))
            span_hours = max(0.0, (t1 - t0).total_seconds() / 3600.0)
        except ValueError:
            span_hours = 0.0
        panels.append(
            {
                "symbol": sym,
                "name": display_name(sym, names) or sym,
                "buy_price": round(buy_price, 6),
                "bought_at": buy_iso,
                "quantity": qty,
                "points": indexed,
                "interval": interval,
                "last": last["close"],
                "first_t": first_t,
                "last_t": last_t,
                "span_hours": round(span_hours, 2),
                "change_pct": round(last["rebased"] - 100, 2),
                "note": "Rebased to your avg buy (100). No forecast.",
            }
        )
    panels.sort(key=lambda p: abs(p["change_pct"]), reverse=True)
    return panels


def _apply_fill_to_lots(
    lots: dict[str, dict[str, float]], trade: dict[str, Any]
) -> None:
    side = str(trade.get("type") or "").upper()
    sym = str(trade.get("symbol") or "")
    if not sym:
        return
    qty = _finite(trade.get("quantity"))
    price = _finite(trade.get("price"))
    if qty <= 0 or price < 0:
        return
    if side == "BUY":
        lot = lots.setdefault(sym, {"qty": 0.0, "cost": 0.0})
        lot["qty"] += qty
        lot["cost"] += qty * price
    elif side == "SELL":
        lot = lots.setdefault(sym, {"qty": 0.0, "cost": 0.0})
        avg = (lot["cost"] / lot["qty"]) if lot["qty"] else price
        lot["qty"] = max(0.0, lot["qty"] - qty)
        lot["cost"] = max(0.0, lot["qty"] * avg)
        if lot["qty"] <= 1e-12:
            lots.pop(sym, None)


def _lots_asof(
    timeline: list[tuple[datetime, dict[str, dict[str, float]]]], when: datetime
) -> dict[str, dict[str, float]]:
    state: dict[str, dict[str, float]] = {}
    for ts, snap in timeline:
        if ts <= when:
            state = snap
        else:
            break
    return {s: dict(v) for s, v in state.items()}


def _close_on_or_before(
    series: list[tuple[datetime, float]], when: datetime
) -> Optional[float]:
    px: Optional[float] = None
    for ts, close in series:
        if ts.date() <= when.date():
            px = close
        else:
            break
    return px


def build_unrealized_curve(
    data_dir: Path, *, days: int = 180, live: Optional[bool] = None
) -> list[dict[str, Any]]:
    """Open-book unrealized € / % vs cost (matches Overview). No forecast."""
    if live is None:
        live = os.getenv("DESK_CHART_LIVE", "1").strip() not in {
            "0",
            "false",
            "False",
            "no",
        }
    portfolio = _load_json(data_dir / "portfolio.json", {})
    holdings = portfolio.get("holdings") or {}
    avg = portfolio.get("avg_buy_price") or {}
    entry_times = _load_json(data_dir / "entry_times.json", {})
    lots: dict[str, dict[str, float]] = {}
    start_ts: Optional[datetime] = None
    for sym, qty in holdings.items():
        q = _finite(qty)
        buy = _finite(avg.get(sym))
        if q <= 0 or buy <= 0:
            continue
        lots[str(sym)] = {"qty": q, "cost": q * buy}
        entry_raw = entry_times.get(sym)
        entry_ts = _finite(entry_raw) if entry_raw not in (None, "") else 0.0
        if entry_ts > 0:
            dt = datetime.fromtimestamp(entry_ts, tz=timezone.utc)
            if start_ts is None or dt < start_ts:
                start_ts = dt

    # Fall back to trade replay when entry_times are missing.
    if not lots:
        trades = _load_jsonl(data_dir / "trades.jsonl")
        replay: dict[str, dict[str, float]] = {}
        for trade in trades:
            ts = _parse_trade_ts(str(trade.get("timestamp") or ""))
            if ts is None:
                continue
            _apply_fill_to_lots(replay, trade)
            if start_ts is None or ts < start_ts:
                start_ts = ts
        lots = replay

    if not lots:
        return []
    if start_ts is None:
        start_ts = datetime.now(timezone.utc)

    price_by_sym: dict[str, list[tuple[datetime, float]]] = {}
    day_set: set = set()
    for sym in lots:
        hist = fetch_price_history(sym, data_dir, days=max(days, 120), live=live)
        series: list[tuple[datetime, float]] = []
        for p in hist:
            ts = _parse_trade_ts(str(p.get("t") or ""))
            close = _finite(p.get("close"), default=float("nan"))
            if ts is None or not math.isfinite(close) or close <= 0:
                continue
            series.append((ts, close))
            day_set.add(ts.date())
        series.sort(key=lambda x: x[0])
        price_by_sym[sym] = series

    start_day = start_ts.date()
    days_sorted = sorted(d for d in day_set if d >= start_day)
    # Anchor at buy day even if bars start later.
    if start_day not in days_sorted:
        days_sorted = [start_day] + days_sorted

    points: list[dict[str, Any]] = []
    for day in days_sorted:
        when = datetime(day.year, day.month, day.day, 23, 59, 59, tzinfo=timezone.utc)
        cost = 0.0
        market_value = 0.0
        active = 0
        for sym, v in lots.items():
            entry_raw = entry_times.get(sym)
            entry_ts = _finite(entry_raw) if entry_raw not in (None, "") else 0.0
            if entry_ts > 0:
                bought = datetime.fromtimestamp(entry_ts, tz=timezone.utc).date()
                if day < bought:
                    continue
            active += 1
            cost += v["cost"]
            px = _close_on_or_before(price_by_sym.get(sym) or [], when)
            if px is None:
                px = (v["cost"] / v["qty"]) if v["qty"] else 0.0
            market_value += v["qty"] * px
        if active == 0 or cost <= 0:
            continue
        unreal = market_value - cost
        points.append(
            {
                "t": when.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "unrealized": round(unreal, 2),
                "unrealized_pct": round((unreal / cost) * 100, 4),
                "cost": round(cost, 2),
                "market_value": round(market_value, 2),
            }
        )

    by_day: dict[str, dict[str, Any]] = {}
    for p in points:
        by_day[p["t"][:10]] = p
    return [by_day[k] for k in sorted(by_day)]


def _latest_scan_breadth_pulse(data_dir: Path) -> dict[str, Any] | None:
    """Latest UTC-day scan-list pulse from Breadth history (display only)."""
    rows = _scan_breadth_history_rows(data_dir)
    if not rows:
        return None
    last = rows[-1]
    return last if isinstance(last, dict) else None


def _scan_breadth_history_rows(data_dir: Path) -> list[dict[str, Any]]:
    """Chronological scan-list daily pulse rows (display only)."""
    rows = _load_json(data_dir / "scan_breadth_daily.json", [])
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict)]

def _book_risk_glance_from_portfolio(data_dir: Path, portfolio: dict[str, Any]) -> dict[str, Any]:
    """Slots/posture glance from cost marks (display only; Book has full strip)."""
    from openbb_backend.desk import build_book_risk_glance

    return build_book_risk_glance(_book_risk_report_from_portfolio(data_dir, portfolio))


def _mark_coverage_from_data(
    data_dir: Path, portfolio: dict[str, Any]
) -> dict[str, Any]:
    """Scan-price coverage (display only). Charts skip live quotes."""
    from openbb_backend.desk import _prices_from_scan, build_mark_coverage

    holdings_raw = portfolio.get("holdings") or {}
    opp, _pin = _load_opportunities(data_dir)
    prices = _prices_from_scan(opp)
    rows: list[dict[str, Any]] = []
    if isinstance(holdings_raw, dict):
        for sym, qty in holdings_raw.items():
            if _finite(qty) <= 0:
                continue
            px = prices.get(str(sym))
            rows.append({"marked": px is not None and px > 0})
    return build_mark_coverage(rows)


def _ledger_health_from_data(data_dir: Path) -> dict[str, Any]:
    from openbb_backend.desk import build_ledger_health

    return build_ledger_health(data_dir)


def _concentration_glance_from_portfolio(
    data_dir: Path, portfolio: dict[str, Any]
) -> dict[str, Any]:
    """Largest-name vs 30% entry cap from cost marks (display only)."""
    from openbb_backend.desk import build_concentration_glance

    return build_concentration_glance(
        _book_risk_report_from_portfolio(data_dir, portfolio)
    )


def _listed_fund_overlap_glance_from_portfolio(
    portfolio: dict[str, Any],
    *,
    concentration_glance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Same-theme ETF/ETC doubles from open holdings (display only)."""
    from openbb_backend.desk import build_listed_fund_overlap_glance

    holdings_raw = portfolio.get("holdings") or {}
    symbols: list[str] = []
    if isinstance(holdings_raw, dict):
        symbols = [str(s) for s in holdings_raw.keys() if str(s).strip()]
    elif isinstance(holdings_raw, list):
        for row in holdings_raw:
            if isinstance(row, dict):
                sym = str(row.get("symbol") or "").strip()
            else:
                sym = str(row or "").strip()
            if sym:
                symbols.append(sym)
    conc = concentration_glance if isinstance(concentration_glance, dict) else {}
    conc_tone = str(conc.get("tone") or "")
    conc_warn: bool | None = (
        bool(conc.get("warn"))
        if conc.get("ready") and conc_tone in {"clear", "warn"}
        else None
    )
    return build_listed_fund_overlap_glance(
        symbols, concentration_warn=conc_warn
    )


def _book_risk_report_from_portfolio(
    data_dir: Path, portfolio: dict[str, Any]
) -> dict[str, Any]:
    """Shared book_risk_report from cost marks (display only)."""
    from stock_checker.risk_halts import book_risk_report
    from stock_checker.trader_config import load_trader_config

    cash = _finite(portfolio.get("cash"))
    holdings_raw = portfolio.get("holdings") or {}
    avg = portfolio.get("avg_buy_price") or {}
    rows: list[dict[str, Any]] = []
    cost = 0.0
    if isinstance(holdings_raw, dict):
        for sym, qty in holdings_raw.items():
            q = _finite(qty)
            px = _finite(avg.get(sym) if isinstance(avg, dict) else 0)
            mv = q * px
            cost += mv
            rows.append({"symbol": str(sym), "market_value": mv})
    equity = cash + cost
    cfg = load_trader_config(data_dir)
    max_pos = int(cfg.get("max_positions") or 5)
    return book_risk_report(
        cash=cash,
        equity=equity,
        holdings=rows,
        max_positions=max_pos,
    )



def _next_buy_glance_from_portfolio(data_dir: Path, portfolio: dict[str, Any]) -> dict[str, Any]:
    """Suggested next-buy € from cost marks (display only; Overview has full block)."""
    from openbb_backend.desk import build_next_buy_glance
    from stock_checker.risk_halts import suggest_entry_notional
    from stock_checker.trader_config import load_trader_config

    cash = _finite(portfolio.get("cash"))
    holdings_raw = portfolio.get("holdings") or {}
    avg = portfolio.get("avg_buy_price") or {}
    cost = 0.0
    open_n = 0
    if isinstance(holdings_raw, dict):
        for sym, qty in holdings_raw.items():
            q = _finite(qty)
            if q <= 0:
                continue
            open_n += 1
            px = _finite(avg.get(sym) if isinstance(avg, dict) else 0)
            cost += q * px
    equity = cash + cost
    cfg = load_trader_config(data_dir)
    max_pos = int(cfg.get("max_positions") or 5)
    return build_next_buy_glance(
        suggest_entry_notional(
            cash=cash,
            equity=equity,
            open_positions=open_n,
            max_positions=max_pos,
            position_size=0.10,
        )
    )


def _soft_gate_runtime_from_config(data_dir: Path) -> dict[str, Any]:
    """Ops soft-gate toggles for soft-allow lead↔config provenance."""
    from stock_checker.trader_config import load_trader_config

    cfg = load_trader_config(data_dir)
    return {
        "regime_gate": bool(cfg.get("regime_gate", True)),
        "rs_gate": bool(cfg.get("rs_gate", True)),
        "breadth_gate": bool(cfg.get("breadth_gate", True)),
        "promote_experiment_strategy": bool(
            cfg.get("promote_experiment_strategy", False)
        ),
    }


def _entry_gates_glance_from_config(data_dir: Path) -> dict[str, Any]:
    """Regime/RS/breadth/promote on/off from Ops file (display only)."""
    from openbb_backend.desk import build_entry_gates_glance

    return build_entry_gates_glance(_soft_gate_runtime_from_config(data_dir))


def _soft_allow_glance_from_data(
    data_dir: Path,
    *,
    scan_time: str = "",
    laya_freshness: str = "",
    debate_freshness: str = "",
) -> dict[str, Any]:
    """Soft-allow glance with Ops toggles for lead↔config clash."""
    from openbb_backend.desk import build_soft_allow_glance
    from stock_checker.gate_audit import enrich_soft_allows, recent_soft_allows

    return build_soft_allow_glance(
        enrich_soft_allows(recent_soft_allows(data_dir, limit=12)),
        scan_time=scan_time,
        laya_freshness=laya_freshness,
        debate_freshness=debate_freshness,
        runtime=_soft_gate_runtime_from_config(data_dir),
    )


def _calm_streak_glance_from_data(data_dir: Path) -> dict[str, Any]:
    """Paper-calm promote-unlock line from paper_calm.json (display only)."""
    from openbb_backend.desk import build_calm_streak_glance

    calm = _load_json(data_dir / "paper_calm.json", {})
    if not isinstance(calm, dict):
        calm = {}
    return build_calm_streak_glance(
        {
            "calm_streak_days": int(calm.get("streak_days") or 0),
            "calm_required_days": int(calm.get("required_days") or 30),
            "calm_ready": bool(calm.get("ready_for_compose_default")),
            "calm_detail": str(calm.get("detail") or ""),
        },
        data_dir=data_dir,
    )


def _promote_ab_glance_from_data(data_dir: Path) -> dict[str, Any]:
    """Promote A/B window line from trader_config + trades (display only)."""
    from openbb_backend.desk import build_promote_ab_glance
    from stock_checker.trader_config import load_trader_config

    cfg = load_trader_config(data_dir)
    portfolio = _load_json(data_dir / "portfolio.json", {})
    holds = portfolio.get("holdings") if isinstance(portfolio, dict) else None
    open_n: int | None = None
    if isinstance(holds, dict):
        open_n = len(holds)
    elif isinstance(holds, list):
        open_n = len(holds)
    return build_promote_ab_glance(
        {
            "promote_experiment_strategy": bool(
                cfg.get("promote_experiment_strategy", False)
            ),
            "max_positions": int(cfg.get("max_positions") or 5),
            "min_hold_hours": float(cfg.get("min_hold_hours") or 24),
            "fee_preset": str(cfg.get("fee_preset") or "revolut_standard"),
            "regime_gate": bool(cfg.get("regime_gate", True)),
            "rs_gate": bool(cfg.get("rs_gate", True)),
            "breadth_gate": bool(cfg.get("breadth_gate", True)),
            "ai_mode": str(cfg.get("ai_mode") or "off"),
            "ai_multi_role": bool(cfg.get("ai_multi_role", True)),
            "open_positions": open_n,
        },
        data_dir=data_dir,
        open_positions=open_n,
    )


def _promote_contract_glance_from_config(data_dir: Path) -> dict[str, Any]:
    """Promote entry-veto contract from Ops file (display only)."""
    from openbb_backend.desk import build_promote_contract_glance
    from stock_checker.trader_config import load_trader_config

    cfg = load_trader_config(data_dir)
    return build_promote_contract_glance(
        {
            "promote_experiment_strategy": bool(
                cfg.get("promote_experiment_strategy", False)
            ),
        }
    )


def _gate_roles_glance_from_config(data_dir: Path) -> dict[str, Any]:
    """Regime vs RS vs breadth role map from Ops file (A14; display only)."""
    from openbb_backend.desk import build_gate_roles_glance
    from stock_checker.trader_config import load_trader_config

    cfg = load_trader_config(data_dir)
    return build_gate_roles_glance(
        {
            "regime_gate": bool(cfg.get("regime_gate", True)),
            "rs_gate": bool(cfg.get("rs_gate", True)),
            "breadth_gate": bool(cfg.get("breadth_gate", True)),
        }
    )


def _crypto_policy_glance_from_portfolio(portfolio: dict[str, Any]) -> dict[str, Any]:
    """Live crypto slot line from portfolio holdings (display only)."""
    from openbb_backend.desk import build_crypto_policy_glance

    holdings_raw = portfolio.get("holdings") or {}
    rows: list[dict[str, Any]] = []
    if isinstance(holdings_raw, dict):
        for sym in holdings_raw.keys():
            s = str(sym or "").strip()
            if s:
                rows.append({"symbol": s})
    elif isinstance(holdings_raw, list):
        rows = [r for r in holdings_raw if isinstance(r, dict)]
    return build_crypto_policy_glance(rows)


def _book_limits_glance_from_config(data_dir: Path) -> dict[str, Any]:
    """Slots · min hold · fee preset from Ops file (display only)."""
    from openbb_backend.desk import build_book_limits_glance
    from stock_checker.trader_config import load_trader_config

    cfg = load_trader_config(data_dir)
    return build_book_limits_glance(
        {
            "max_positions": cfg.get("max_positions"),
            "min_hold_hours": cfg.get("min_hold_hours"),
            "fee_preset": cfg.get("fee_preset"),
        }
    )


def _loop_cadence_glance_from_config(_data_dir: Path) -> dict[str, Any]:
    """Scan / trade loop floors — match desk compose display defaults."""
    from openbb_backend.desk import build_loop_cadence_glance

    return build_loop_cadence_glance(
        {"scan_interval_min": 15, "trade_interval_min": 5}
    )


def _improve_tick_glance_from_data(
    data_dir: Path, *, scan_time: str = ""
) -> dict[str, Any]:
    """Last Cursor improve tick age — match desk overnight honesty."""
    from openbb_backend.desk import build_improve_tick_glance
    from stock_checker.trader_config import load_trader_config

    cfg = load_trader_config(data_dir)
    try:
        scan_m = int(cfg.get("scan_interval_min") or 15)
    except (TypeError, ValueError):
        scan_m = 15
    return build_improve_tick_glance(
        data_dir,
        scan_time=scan_time,
        scan_interval_sec=max(60, scan_m * 60),
    )


def _ai_mode_glance_from_config(data_dir: Path) -> dict[str, Any]:
    """AI mode · model · multi-role from Ops file (display only)."""
    from openbb_backend.desk import build_ai_mode_glance
    from stock_checker.trader_config import load_trader_config

    cfg = load_trader_config(data_dir)
    return build_ai_mode_glance(
        {
            "ai_mode": cfg.get("ai_mode"),
            "ai_model": cfg.get("ai_model"),
            "ai_multi_role": cfg.get("ai_multi_role", True),
        }
    )


def _ai_validate_scope_glance_from_config(data_dir: Path) -> dict[str, Any]:
    """AI top-N validate scope from Ops file (display only)."""
    from openbb_backend.desk import build_ai_validate_scope_glance
    from stock_checker.trader_config import load_trader_config

    cfg = load_trader_config(data_dir)
    return build_ai_validate_scope_glance({"ai_mode": cfg.get("ai_mode")})


def _rebuy_cooldown_glance_from_data(data_dir: Path) -> dict[str, Any]:
    """Anti flip-flop rebuy cooldown from exit_times.json (display only)."""
    from openbb_backend.desk import build_rebuy_cooldown_glance
    from stock_checker.trader_config import load_trader_config

    cfg = load_trader_config(data_dir)
    exit_times = _load_json(data_dir / "exit_times.json", {})
    if not isinstance(exit_times, dict):
        exit_times = {}
    hold_h = float(cfg.get("min_hold_hours") or 24)
    return build_rebuy_cooldown_glance(
        exit_times,
        cooldown_seconds=max(0.0, hold_h) * 3600.0,
    )


def _daily_loss_glance_from_data(
    data_dir: Path, portfolio: dict[str, Any]
) -> dict[str, Any]:
    """UTC-day realized vs −2% soft halt from trades.jsonl (display only)."""
    from openbb_backend.desk import build_daily_loss_glance
    from stock_checker.risk_halts import realized_pnl_for_utc_day

    initial = float(portfolio.get("initial_cash") or 0)
    return build_daily_loss_glance(realized_pnl_for_utc_day(data_dir), initial)


def _post_sl_cooldown_glance_from_data(data_dir: Path) -> dict[str, Any]:
    """Post-SL buy cooldown from last stop-loss sell (display only)."""
    from openbb_backend.desk import build_post_sl_cooldown_glance
    from stock_checker.risk_halts import latest_stop_loss_sell

    hit = latest_stop_loss_sell(data_dir)
    if hit is None:
        return build_post_sl_cooldown_glance(None, None)
    return build_post_sl_cooldown_glance(hit[0], hit[1])


def _fee_burn_glance_from_portfolio(
    data_dir: Path, portfolio: dict[str, Any]
) -> dict[str, Any]:
    """Fee-drag % of start + vs realized sell P&L (display only)."""
    from openbb_backend.desk import build_fee_burn_glance

    fees = float(portfolio.get("total_fees_paid") or 0)
    initial = float(portfolio.get("initial_cash") or 0)
    trades = _load_jsonl(data_dir / "trades.jsonl")
    sells = [
        t
        for t in trades
        if isinstance(t, dict) and str(t.get("type") or "").upper() == "SELL"
    ]
    realized: float | None = None
    if sells:
        realized = sum(float(t.get("profit_loss") or 0) for t in sells)
    return build_fee_burn_glance(fees, initial, realized_pnl=realized)


def _fee_allowance_glance_from_data(data_dir: Path) -> dict[str, Any]:
    """Free monthly legs left from portfolio + Ops fee preset (display only)."""
    from openbb_backend.desk import build_fee_allowance_glance
    from stock_checker.trader_config import load_trader_config

    portfolio = _load_json(data_dir / "portfolio.json", {})
    if not isinstance(portfolio, dict):
        portfolio = {}
    cfg = load_trader_config(data_dir)
    try:
        free_legs = int(
            portfolio.get("free_legs_per_month")
            or cfg.get("free_legs_per_month")
            or 0
        )
    except (TypeError, ValueError):
        free_legs = 0
    try:
        allowance_used = int(portfolio.get("fee_allowance_used") or 0)
    except (TypeError, ValueError):
        allowance_used = 0
    allowance_month = str(portfolio.get("fee_allowance_month") or "")
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    if allowance_month != current_month:
        allowance_used = 0
    return build_fee_allowance_glance(
        {
            "fee_preset": cfg.get("fee_preset") or "revolut_standard",
            "free_legs_per_month": max(0, free_legs),
            "fee_allowance_used": max(0, allowance_used),
            "fee_allowance_remaining": max(0, free_legs - allowance_used),
            "fee_allowance_month": current_month,
        }
    )


def _stuck_capital_glance_from_data(data_dir: Path) -> dict[str, Any]:
    """A15 min-hold underwater glance from portfolio + scan marks (display only)."""
    import time

    from openbb_backend.desk import (
        _fmt_hold,
        _prices_from_scan,
        build_stuck_capital_glance,
    )
    from stock_checker.trader_config import load_trader_config

    portfolio = _load_json(data_dir / "portfolio.json", {})
    if not isinstance(portfolio, dict):
        portfolio = {}
    entry_times = _load_json(data_dir / "entry_times.json", {})
    if not isinstance(entry_times, dict):
        entry_times = {}
    opp, _pin = _load_opportunities(data_dir)
    cfg = load_trader_config(data_dir)
    min_hold_s = max(4.0, float(cfg.get("min_hold_hours") or 24)) * 3600.0
    holdings = portfolio.get("holdings") or {}
    avg = portfolio.get("avg_buy_price") or {}
    if not isinstance(holdings, dict) or not isinstance(avg, dict):
        return build_stuck_capital_glance([])
    marks = _prices_from_scan(opp)
    now = time.time()
    stuck: list[dict[str, Any]] = []
    for sym, qty in holdings.items():
        try:
            q = float(qty)
            buy = float(avg.get(sym) or 0)
        except (TypeError, ValueError):
            continue
        if q <= 0 or buy <= 0:
            continue
        last = float(marks.get(str(sym)) or 0) or buy
        unreal_pct = ((last - buy) / buy) * 100.0
        try:
            entry_ts = float(entry_times.get(sym) or 0) or None
        except (TypeError, ValueError):
            entry_ts = None
        if not entry_ts:
            continue
        held_s = now - entry_ts
        if held_s >= min_hold_s and unreal_pct < 0:
            stuck.append(
                {
                    "symbol": str(sym),
                    "unrealized_pct": unreal_pct,
                    "held": _fmt_hold(held_s),
                    "held_seconds": held_s,
                }
            )
    return build_stuck_capital_glance(stuck)



def _book_posture_glance_from_data(data_dir: Path) -> dict[str, Any]:
    """Live posture slots from portfolio (no cost-flat trim guess; display only)."""
    from openbb_backend.desk import build_book_posture_glance
    from stock_checker.trader_config import load_trader_config

    portfolio = _load_json(data_dir / "portfolio.json", {})
    if not isinstance(portfolio, dict):
        portfolio = {}
    cfg = load_trader_config(data_dir)
    try:
        max_pos = int(cfg.get("max_positions") or 5)
    except (TypeError, ValueError):
        max_pos = 5
    try:
        min_hold_h = float(cfg.get("min_hold_hours") or 24)
    except (TypeError, ValueError):
        min_hold_h = 24.0
    holdings = portfolio.get("holdings") or {}
    rows: list[dict[str, Any]] = []
    if isinstance(holdings, dict):
        for sym, qty in holdings.items():
            try:
                q = float(qty)
            except (TypeError, ValueError):
                continue
            if q <= 0:
                continue
            rows.append({"symbol": str(sym), "held_seconds": 0.0})
    return build_book_posture_glance(
        rows,
        max_positions=max_pos,
        min_hold_hours=min_hold_h,
        suggest_trim=False,
    )


def _min_hold_lock_glance_from_data(data_dir: Path) -> dict[str, Any]:
    """Open lots still inside min-hold (display only; pairs with stuck-capital)."""
    import time

    from openbb_backend.desk import build_min_hold_lock_glance
    from stock_checker.trader_config import load_trader_config

    portfolio = _load_json(data_dir / "portfolio.json", {})
    if not isinstance(portfolio, dict):
        portfolio = {}
    entry_times = _load_json(data_dir / "entry_times.json", {})
    if not isinstance(entry_times, dict):
        entry_times = {}
    cfg = load_trader_config(data_dir)
    try:
        min_hold_h = float(cfg.get("min_hold_hours") or 24)
    except (TypeError, ValueError):
        min_hold_h = 24.0
    holdings = portfolio.get("holdings") or {}
    if not isinstance(holdings, dict):
        return build_min_hold_lock_glance([], min_hold_hours=min_hold_h)
    now = time.time()
    rows: list[dict[str, Any]] = []
    for sym, qty in holdings.items():
        try:
            q = float(qty)
        except (TypeError, ValueError):
            continue
        if q <= 0:
            continue
        try:
            entry_ts = float(entry_times.get(sym) or 0) or None
        except (TypeError, ValueError):
            entry_ts = None
        if not entry_ts:
            continue
        rows.append(
            {
                "symbol": str(sym),
                "held_seconds": max(0.0, now - entry_ts),
            }
        )
    return build_min_hold_lock_glance(rows, min_hold_hours=min_hold_h)


def _postmortem_glance_from_data(data_dir: Path) -> dict[str, Any]:
    """Newest closed-round glance from trades.jsonl (display only)."""
    from openbb_backend.desk import build_postmortem_glance
    from stock_checker.trade_postmortem import DEFAULT_LIMIT as POSTMORTEM_LIMIT
    from stock_checker.trade_postmortem import closed_rounds

    trades = _load_jsonl(data_dir / "trades.jsonl")
    return build_postmortem_glance(closed_rounds(trades, limit=POSTMORTEM_LIMIT))


def load_chart_payload(data_dir: Path) -> dict[str, Any]:
    # Local import keeps charts free of desk module load at import time.
    from openbb_backend.desk import (
        build_breadth_glance,
        build_breakout_guard_glance,
        build_earnings_blackout_glance,
        build_equity_hours_glance,
        build_exit_policy_glance,
        build_junk_filter_glance,
        build_loss_rotation_glance,
        build_stale_rotation_glance,
        build_ai_roles_glance,
        build_laya_glance,
        build_ai_debate_glance,
        build_gate_params_glance,
        build_universe_discovery_glance,
        build_atr_display_glance,
        build_entry_slots_glance,
        build_pretrade_glance,
        build_scan_freshness,
        build_session_glance,
        policy_honesty_fold_meta,
        memory_advisory_clock_tones,
        scan_list_rows,
    )
    from stock_checker.risk_halts import pretrade_status

    opp, archive_res = _load_opportunities(data_dir)
    scan_time = str(opp.get("scan_time") or "")
    portfolio = _load_json(data_dir / "portfolio.json", {})
    if not isinstance(portfolio, dict):
        portfolio = {}
    initial = float(portfolio.get("initial_cash") or 0)
    pretrade_level, pretrade_notes = pretrade_status(data_dir, initial_cash=initial)
    laya_tone, debate_tone = memory_advisory_clock_tones(data_dir)
    price_panels = build_price_panels(data_dir)
    concentration_glance = _concentration_glance_from_portfolio(
        data_dir, portfolio
    )
    listed_fund_overlap_glance = _listed_fund_overlap_glance_from_portfolio(
        portfolio, concentration_glance=concentration_glance
    )
    from openbb_backend.desk import attach_concentration_funds_lean

    concentration_glance = attach_concentration_funds_lean(
        concentration_glance, listed_fund_overlap_glance
    )

    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "equity": build_equity_curve(data_dir),
        "unrealized": build_unrealized_curve(data_dir),
        "allocation": build_allocation(data_dir),
        "prices": price_panels,
        "price_bars_glance": chart_price_bars_glance(price_panels),
        "from_buy": build_from_buy_panels(data_dir),
        "breadth_glance": build_breadth_glance(
            _latest_scan_breadth_pulse(data_dir),
            history=_scan_breadth_history_rows(data_dir),
        ),
        "scan_freshness": build_scan_freshness(
            scan_time,
            archive_pin=str(archive_res.get("pin") or ""),
            archive_pin_bit=str(archive_res.get("bit") or ""),
            archive_pin_bit_core=str(
                archive_res.get("bit_core") or archive_res.get("bit") or ""
            ),
            archive_pin_lean=str(archive_res.get("pin_lean") or ""),
            archive_pin_lean_warn=bool(archive_res.get("pin_lean_warn")),
            archive_pin_warn=bool(archive_res.get("warn")),
        ),
        "pretrade_glance": build_pretrade_glance(pretrade_level, pretrade_notes),
        "next_buy_glance": _next_buy_glance_from_portfolio(data_dir, portfolio),
        "soft_allow_glance": _soft_allow_glance_from_data(
            data_dir,
            scan_time=scan_time,
            laya_freshness=laya_tone,
            debate_freshness=debate_tone,
        ),
        "entry_gates_glance": _entry_gates_glance_from_config(data_dir),
        "calm_streak_glance": _calm_streak_glance_from_data(data_dir),
        "promote_ab_glance": _promote_ab_glance_from_data(data_dir),
        "crypto_policy_glance": _crypto_policy_glance_from_portfolio(portfolio),
        "exit_policy_glance": build_exit_policy_glance(),
        "earnings_blackout_glance": build_earnings_blackout_glance(),
        "ai_mode_glance": _ai_mode_glance_from_config(data_dir),
        "ai_roles_glance": build_ai_roles_glance(),
        "laya_glance": build_laya_glance(data_dir, scan_time=scan_time),
        "ai_debate_glance": build_ai_debate_glance(data_dir, scan_time=scan_time),
        "ai_validate_scope_glance": _ai_validate_scope_glance_from_config(data_dir),
        "session_glance": build_session_glance(),
        "equity_hours_glance": build_equity_hours_glance(),
        "breakout_guard_glance": build_breakout_guard_glance(),
        "loss_rotation_glance": build_loss_rotation_glance(),
        "stale_rotation_glance": build_stale_rotation_glance(),
        "book_posture_glance": _book_posture_glance_from_data(data_dir),
        "junk_filter_glance": build_junk_filter_glance(),
        "universe_discovery_glance": build_universe_discovery_glance(data_dir),
        "atr_display_glance": build_atr_display_glance(
            scan_list_rows(opp.get("crypto_leaders"))
            + scan_list_rows(opp.get("stock_breakouts"))
            + scan_list_rows(opp.get("recommendations"))
        ),
        "entry_slots_glance": build_entry_slots_glance(),
        "promote_contract_glance": _promote_contract_glance_from_config(data_dir),
        "gate_roles_glance": _gate_roles_glance_from_config(data_dir),
        "gate_params_glance": build_gate_params_glance(),
        "book_limits_glance": _book_limits_glance_from_config(data_dir),
        "rebuy_cooldown_glance": _rebuy_cooldown_glance_from_data(data_dir),
        "daily_loss_glance": _daily_loss_glance_from_data(data_dir, portfolio),
        "concentration_glance": concentration_glance,
        "listed_fund_overlap_glance": listed_fund_overlap_glance,
        "post_sl_cooldown_glance": _post_sl_cooldown_glance_from_data(data_dir),
        "loop_cadence_glance": _loop_cadence_glance_from_config(data_dir),
        "improve_tick_glance": _improve_tick_glance_from_data(
            data_dir, scan_time=scan_time
        ),
        "fee_allowance_glance": _fee_allowance_glance_from_data(data_dir),
        "fee_burn_glance": _fee_burn_glance_from_portfolio(data_dir, portfolio),
        "stuck_capital_glance": _stuck_capital_glance_from_data(data_dir),
        "min_hold_lock_glance": _min_hold_lock_glance_from_data(data_dir),
        "postmortem_glance": _postmortem_glance_from_data(data_dir),
        "book_risk_glance": _book_risk_glance_from_portfolio(data_dir, portfolio),
        "mark_coverage": _mark_coverage_from_data(data_dir, portfolio),
        "ledger_health": _ledger_health_from_data(data_dir),
    }
    # Charts JS reads these; a missing key fell back to the static category
    # index and hid a hot fee / stale Yahoo glance inside the fold.
    meta, warn = policy_honesty_fold_meta(payload)
    payload["policy_honesty_meta"] = meta
    payload["policy_honesty_warn"] = warn
    return payload
