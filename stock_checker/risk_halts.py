"""
Soft risk halts for paper entries (daily loss + concentration).

Does not change exits. Fail-open on unreadable trade logs.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Tuple

from stock_checker.market_hours import (
    is_crypto_symbol,
    is_equity_session_closed,
    is_german_equity,
)

# Realized loss vs initial capital (UTC day) → block new buys.
DEFAULT_DAILY_LOSS_PCT = 2.0
# Cap one new fill notional vs marked equity.
DEFAULT_MAX_NAME_PCT = 30.0
# After a stop-loss sell, block new buys (anti revenge refill). Floor matches trader.
DEFAULT_POST_SL_COOLDOWN_SEC = 4 * 3600
# Hold-tenure buckets for Group Matrix–lite marks (not calendar market 1w/1m).
TENURE_WEEK_SEC = 7 * 86400
TENURE_MONTH_SEC = 30 * 86400
# Exit-band zone: fraction of asset TP/SL before counting as near-exit (display).
EXIT_BAND_ZONE_FRAC = 0.75
# Screener score bands for Group Matrix (match recommender BUY thresholds).
SCAN_SCORE_HI = 50.0
SCAN_SCORE_MID = 25.0
# pct_from_high bands (match scanner breakout ≥ −5%; mid floor −20%).
SCAN_NEAR_HIGH_PCT = -5.0
SCAN_NEAR_HIGH_MID = -20.0
# StockBee-lite ±4% day movers (match Breadth crypto_big / mover ratio).
SCAN_MOVER_PCT = 4.0
# Rebuy gap vs anti flip-flop cooldown (match Ops default min hold 24h).
DEFAULT_REBUY_COOLDOWN_SEC = 24 * 3600
# Entry cash-fraction vs sizer default (~10% of cash) — Group Matrix Buy-%.
DEFAULT_ENTRY_CASH_FRAC = 0.10
ENTRY_SIZE_FAT_FRAC = 0.15  # ≥1.5× default
ENTRY_SIZE_THIN_FRAC = 0.05  # <0.5× default


def utc_day_key(when: Optional[datetime] = None) -> str:
    dt = when or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d")


def _parse_trade_dt(timestamp: str) -> Optional[datetime]:
    """Best-effort aware UTC datetime from trade timestamp strings."""
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
        return dt.astimezone(timezone.utc)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                piece = raw[:19] if len(raw) >= 19 else raw
                return datetime.strptime(piece, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return None


def _parse_trade_day(timestamp: str) -> Optional[str]:
    """Best-effort UTC calendar day from trade timestamp strings."""
    dt = _parse_trade_dt(timestamp)
    if dt is not None:
        return dt.strftime("%Y-%m-%d")
    raw = str(timestamp or "").strip()
    if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
        return raw[:10]
    return None


def _parse_trade_epoch(timestamp: str) -> Optional[float]:
    """Unix epoch seconds from a trade timestamp, or None."""
    dt = _parse_trade_dt(timestamp)
    if dt is None:
        return None
    return dt.timestamp()


def latest_stop_loss_sell(
    data_dir: Path | str,
) -> Optional[Tuple[str, float]]:
    """Most recent SELL with exit_reason ``sl`` → (symbol, epoch)."""
    best: Optional[Tuple[str, float]] = None
    for row in iter_trades(data_dir):
        if str(row.get("type") or "").upper() != "SELL":
            continue
        reason = str(row.get("exit_reason") or "").strip().lower()
        if reason != "sl":
            continue
        epoch = _parse_trade_epoch(str(row.get("timestamp") or ""))
        if epoch is None:
            continue
        sym = str(row.get("symbol") or "").strip().upper()
        if best is None or epoch > best[1]:
            best = (sym, epoch)
    return best


def post_sl_buy_block_until(
    data_dir: Path | str,
    *,
    cooldown_seconds: float = DEFAULT_POST_SL_COOLDOWN_SEC,
) -> float:
    """Epoch until which desk/pretrade should treat post-SL cooldown as active.

    Derived from the last stop-loss sell on disk (trader also keeps in-memory
    ``_buy_block_until``). Fail-open → 0 when no SL or unreadable logs.
    """
    try:
        cd = float(cooldown_seconds)
    except (TypeError, ValueError):
        cd = float(DEFAULT_POST_SL_COOLDOWN_SEC)
    if cd <= 0:
        return 0.0
    hit = latest_stop_loss_sell(data_dir)
    if hit is None:
        return 0.0
    return float(hit[1]) + cd


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


def _format_mark_pct(
    pct: float | None,
    *,
    has_lots: bool,
    any_marked: bool,
    cluster_n: int = 0,
) -> str:
    """Sleeve mark label — missing marks are — not 0 (Group Matrix honesty).

    ``cluster_n`` is names that feed the shown figure: marked count when a %
    is shown, else lots in the bucket for —. xang1234 cluster size adapted.
    """
    if not has_lots:
        return ""
    n_bit = f"×{cluster_n}" if cluster_n > 0 else ""
    if not any_marked or pct is None:
        return f"—{n_bit}" if n_bit else "—"
    sign = "+" if pct >= 0 else "−"
    return f"{sign}{abs(pct):.1f}%{n_bit}"


def _holding_cost_basis(h: dict[str, Any]) -> float:
    try:
        basis = float(h.get("cost_basis") or 0.0)
    except (TypeError, ValueError):
        basis = 0.0
    if basis > 0:
        return basis
    try:
        return float(h.get("market_value") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _holding_marked_pct(h: dict[str, Any]) -> float | None:
    """Since-buy unrealized % when the row is marked; else None."""
    marked = h.get("marked")
    if marked is None:
        # Explicit unrealized_pct without marked flag still counts
        # only when the key is present (cost-flat chart rows omit it).
        marked = "unrealized_pct" in h
    if not marked:
        return None
    try:
        return float(h.get("unrealized_pct"))
    except (TypeError, ValueError):
        return None


def sleeve_mark_returns(holdings: list[dict[str, Any]]) -> dict[str, Any]:
    """Cost-weighted mark % by equity/crypto sleeve (display only).

    xang1234 Group Matrix adapted: sleeve groups + missing ≠ zero +
    cluster n (×N marked names in the %). Not calendar 1w/1m.
    """
    sleeves: dict[str, dict[str, Any]] = {
        "equity": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "crypto": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
    }
    for h in holdings:
        if not isinstance(h, dict):
            continue
        sym = str(h.get("symbol") or "")
        kind = str(h.get("kind") or "")
        if not kind:
            kind = "crypto" if "-USD" in sym else "stock"
        sleeve = "crypto" if kind == "crypto" else "equity"
        basis = _holding_cost_basis(h)
        if basis <= 0:
            continue
        bucket = sleeves[sleeve]
        bucket["lots"] += 1
        pct = _holding_marked_pct(h)
        if pct is None:
            continue
        bucket["marked"] += 1
        bucket["cost"] += basis
        bucket["w_pct"] += basis * pct

    out: dict[str, Any] = {
        "equity_mark_pct": None,
        "crypto_mark_pct": None,
        "equity_mark_label": "",
        "crypto_mark_label": "",
        "sleeve_marks_ready": False,
        "sleeve_marks_bit": "",
        "equity_lots": 0,
        "crypto_lots": 0,
        "equity_marked": 0,
        "crypto_marked": 0,
    }
    bits: list[str] = []
    for key, short in (("equity", "eq"), ("crypto", "cr")):
        bucket = sleeves[key]
        has_lots = int(bucket["lots"]) > 0
        any_marked = int(bucket["marked"]) > 0
        pct: float | None = None
        if any_marked and float(bucket["cost"]) > 0:
            pct = float(bucket["w_pct"]) / float(bucket["cost"])
        cluster_n = int(bucket["marked"] if any_marked else bucket["lots"])
        label = _format_mark_pct(
            pct, has_lots=has_lots, any_marked=any_marked, cluster_n=cluster_n
        )
        out[f"{key}_lots"] = int(bucket["lots"])
        out[f"{key}_marked"] = int(bucket["marked"])
        out[f"{key}_mark_pct"] = round(pct, 2) if pct is not None else None
        out[f"{key}_mark_label"] = label
        if label:
            bits.append(f"{short} {label}")
    if bits:
        out["sleeve_marks_ready"] = True
        out["sleeve_marks_bit"] = "marks " + " / ".join(bits)
    return out


def _tenure_bucket(held_seconds: float | None) -> str | None:
    """Map hold age to week/month tenure key; None when age unknown."""
    if held_seconds is None:
        return None
    try:
        held = float(held_seconds)
    except (TypeError, ValueError):
        return None
    if held < 0:
        return None
    if held < TENURE_WEEK_SEC:
        return "lt_7d"
    if held < TENURE_MONTH_SEC:
        return "7_30d"
    return "ge_30d"


def tenure_mark_returns(holdings: list[dict[str, Any]]) -> dict[str, Any]:
    """Cost-weighted since-buy mark % by hold tenure (display only).

    xang1234 weekly/monthly Group Matrix adapted as hold-age buckets
    (<7d / 7–30d / ≥30d) + cluster n. Not calendar 1w/1m. Missing age or mark → —.
    """
    buckets: dict[str, dict[str, Any]] = {
        "lt_7d": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "7_30d": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "ge_30d": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
    }
    unknown_lots = 0
    for h in holdings:
        if not isinstance(h, dict):
            continue
        basis = _holding_cost_basis(h)
        if basis <= 0:
            continue
        held_raw = h.get("held_seconds")
        key = _tenure_bucket(held_raw if held_raw is not None else None)
        if key is None:
            unknown_lots += 1
            continue
        bucket = buckets[key]
        bucket["lots"] += 1
        pct = _holding_marked_pct(h)
        if pct is None:
            continue
        bucket["marked"] += 1
        bucket["cost"] += basis
        bucket["w_pct"] += basis * pct

    out: dict[str, Any] = {
        "tenure_lt_7d_pct": None,
        "tenure_7_30d_pct": None,
        "tenure_ge_30d_pct": None,
        "tenure_lt_7d_label": "",
        "tenure_7_30d_label": "",
        "tenure_ge_30d_label": "",
        "tenure_marks_ready": False,
        "tenure_marks_bit": "",
        "tenure_unknown_lots": unknown_lots,
        "tenure_lt_7d_lots": 0,
        "tenure_7_30d_lots": 0,
        "tenure_ge_30d_lots": 0,
    }
    bits: list[str] = []
    for key, short, field in (
        ("lt_7d", "<7d", "tenure_lt_7d"),
        ("7_30d", "7–30d", "tenure_7_30d"),
        ("ge_30d", "≥30d", "tenure_ge_30d"),
    ):
        bucket = buckets[key]
        has_lots = int(bucket["lots"]) > 0
        any_marked = int(bucket["marked"]) > 0
        pct: float | None = None
        if any_marked and float(bucket["cost"]) > 0:
            pct = float(bucket["w_pct"]) / float(bucket["cost"])
        cluster_n = int(bucket["marked"] if any_marked else bucket["lots"])
        label = _format_mark_pct(
            pct, has_lots=has_lots, any_marked=any_marked, cluster_n=cluster_n
        )
        out[f"{field}_lots"] = int(bucket["lots"])
        out[f"{field}_pct"] = round(pct, 2) if pct is not None else None
        out[f"{field}_label"] = label
        if label:
            bits.append(f"{short} {label}")
    if bits:
        out["tenure_marks_ready"] = True
        out["tenure_marks_bit"] = "tenure " + " · ".join(bits)
    return out


def polarity_mark_returns(holdings: list[dict[str, Any]]) -> dict[str, Any]:
    """Cost-weighted since-buy mark % for winners vs losers (display only).

    xang1234 Group Matrix green→red cluster edge adapted as book polarity:
    marked lots with unrealized >0 vs <0. Flat 0% and unmarked do not dilute.
    Cluster n is marked names in each side. Not calendar returns; not a gate.
    """
    sides: dict[str, dict[str, Any]] = {
        "win": {"cost": 0.0, "w_pct": 0.0, "lots": 0},
        "lose": {"cost": 0.0, "w_pct": 0.0, "lots": 0},
    }
    flat_lots = 0
    unmarked_lots = 0
    for h in holdings:
        if not isinstance(h, dict):
            continue
        basis = _holding_cost_basis(h)
        if basis <= 0:
            continue
        pct = _holding_marked_pct(h)
        if pct is None:
            unmarked_lots += 1
            continue
        if pct > 0:
            key = "win"
        elif pct < 0:
            key = "lose"
        else:
            flat_lots += 1
            continue
        bucket = sides[key]
        bucket["lots"] += 1
        bucket["cost"] += basis
        bucket["w_pct"] += basis * pct

    out: dict[str, Any] = {
        "polarity_win_pct": None,
        "polarity_lose_pct": None,
        "polarity_win_label": "",
        "polarity_lose_label": "",
        "polarity_win_lots": int(sides["win"]["lots"]),
        "polarity_lose_lots": int(sides["lose"]["lots"]),
        "polarity_flat_lots": flat_lots,
        "polarity_unmarked_lots": unmarked_lots,
        "polarity_marks_ready": False,
        "polarity_marks_bit": "",
    }
    bits: list[str] = []
    for key, short, field in (
        ("win", "win", "polarity_win"),
        ("lose", "lose", "polarity_lose"),
    ):
        bucket = sides[key]
        has_lots = int(bucket["lots"]) > 0
        pct: float | None = None
        if has_lots and float(bucket["cost"]) > 0:
            pct = float(bucket["w_pct"]) / float(bucket["cost"])
        n_lots = int(bucket["lots"])
        label = _format_mark_pct(
            pct, has_lots=has_lots, any_marked=has_lots, cluster_n=n_lots
        )
        out[f"{field}_pct"] = round(pct, 2) if pct is not None else None
        out[f"{field}_label"] = label
        if label:
            bits.append(f"{short} {label}")
    if bits:
        out["polarity_marks_ready"] = True
        out["polarity_marks_bit"] = "polarity " + " · ".join(bits)
    return out


def size_mark_returns(holdings: list[dict[str, Any]]) -> dict[str, Any]:
    """Cost-weighted since-buy mark % by position size (display only).

    xang1234 Group Matrix size cluster adapted: split lots at median cost
    into large vs small + cluster n. Needs ≥2 costed lots. Missing mark → —.
    Not a gate; not calendar market returns.
    """
    empty: dict[str, Any] = {
        "size_large_pct": None,
        "size_small_pct": None,
        "size_large_label": "",
        "size_small_label": "",
        "size_large_lots": 0,
        "size_small_lots": 0,
        "size_marks_ready": False,
        "size_marks_bit": "",
    }
    lots: list[tuple[float, dict[str, Any]]] = []
    for h in holdings:
        if not isinstance(h, dict):
            continue
        basis = _holding_cost_basis(h)
        if basis <= 0:
            continue
        lots.append((basis, h))
    if len(lots) < 2:
        return empty

    lots.sort(key=lambda row: row[0])
    mid = len(lots) // 2
    sides: dict[str, dict[str, Any]] = {
        "small": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "large": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
    }
    for i, (basis, h) in enumerate(lots):
        key = "small" if i < mid else "large"
        bucket = sides[key]
        bucket["lots"] += 1
        pct = _holding_marked_pct(h)
        if pct is None:
            continue
        bucket["marked"] += 1
        bucket["cost"] += basis
        bucket["w_pct"] += basis * pct

    out: dict[str, Any] = {
        **empty,
        "size_large_lots": int(sides["large"]["lots"]),
        "size_small_lots": int(sides["small"]["lots"]),
    }
    bits: list[str] = []
    for key, short, field in (
        ("large", "lg", "size_large"),
        ("small", "sm", "size_small"),
    ):
        bucket = sides[key]
        has_lots = int(bucket["lots"]) > 0
        any_marked = int(bucket["marked"]) > 0
        pct: float | None = None
        if any_marked and float(bucket["cost"]) > 0:
            pct = float(bucket["w_pct"]) / float(bucket["cost"])
        cluster_n = int(bucket["marked"] if any_marked else bucket["lots"])
        label = _format_mark_pct(
            pct, has_lots=has_lots, any_marked=any_marked, cluster_n=cluster_n
        )
        out[f"{field}_pct"] = round(pct, 2) if pct is not None else None
        out[f"{field}_label"] = label
        if label:
            bits.append(f"{short} {label}")
    if bits:
        out["size_marks_ready"] = True
        out["size_marks_bit"] = "size " + " · ".join(bits)
    return out


def leader_mark_returns(holdings: list[dict[str, Any]]) -> dict[str, Any]:
    """Cost-weighted since-buy mark % for top lot vs rest (display only).

    xang1234 Group Matrix + portfolio AI concentration cluster: the single
    largest cost basis name vs the remaining book + rest cluster n.
    Needs ≥2 costed lots. Missing mark → —. Not a gate; not calendar returns.
    """
    empty: dict[str, Any] = {
        "leader_symbol": "",
        "leader_mark_pct": None,
        "leader_rest_pct": None,
        "leader_mark_label": "",
        "leader_rest_label": "",
        "leader_lots": 0,
        "leader_rest_lots": 0,
        "leader_marks_ready": False,
        "leader_marks_bit": "",
    }
    lots: list[tuple[float, dict[str, Any]]] = []
    for h in holdings:
        if not isinstance(h, dict):
            continue
        basis = _holding_cost_basis(h)
        if basis <= 0:
            continue
        lots.append((basis, h))
    if len(lots) < 2:
        return empty

    lots.sort(key=lambda row: row[0], reverse=True)
    top_basis, top_h = lots[0]
    rest = lots[1:]
    top_sym = str(top_h.get("symbol") or "").strip().upper()
    top_pct = _holding_marked_pct(top_h)
    rest_cost = 0.0
    rest_w = 0.0
    rest_marked = 0
    for basis, h in rest:
        pct = _holding_marked_pct(h)
        if pct is None:
            continue
        rest_marked += 1
        rest_cost += basis
        rest_w += basis * pct
    rest_pct: float | None = None
    if rest_marked > 0 and rest_cost > 0:
        rest_pct = rest_w / rest_cost

    top_label = _format_mark_pct(
        top_pct,
        has_lots=True,
        any_marked=top_pct is not None,
        cluster_n=1,
    )
    rest_n = rest_marked if rest_marked > 0 else len(rest)
    rest_label = _format_mark_pct(
        rest_pct,
        has_lots=len(rest) > 0,
        any_marked=rest_marked > 0,
        cluster_n=rest_n,
    )
    bits: list[str] = []
    if top_label:
        head = f"{top_sym} {top_label}" if top_sym else top_label
        bits.append(f"top {head}")
    if rest_label:
        bits.append(f"rest {rest_label}")
    total_cost = sum(b for b, _ in lots)
    cost_share = (top_basis / total_cost * 100.0) if total_cost > 0 else 0.0
    out: dict[str, Any] = {
        **empty,
        "leader_symbol": top_sym,
        "leader_mark_pct": round(top_pct, 2) if top_pct is not None else None,
        "leader_rest_pct": round(rest_pct, 2) if rest_pct is not None else None,
        "leader_mark_label": top_label,
        "leader_rest_label": rest_label,
        "leader_lots": 1,
        "leader_rest_lots": len(rest),
        "leader_cost_share": round(cost_share, 1),
    }
    if bits:
        out["leader_marks_ready"] = True
        out["leader_marks_bit"] = "leader " + " · ".join(bits)
    return out


def _venue_bucket(h: dict[str, Any]) -> str:
    """US cash vs Xetra `.DE` vs crypto — Group Matrix country/exchange lite."""
    sym = str(h.get("symbol") or "")
    kind = str(h.get("kind") or "")
    if not kind:
        kind = "crypto" if is_crypto_symbol(sym) else "stock"
    if kind == "crypto" or is_crypto_symbol(sym):
        return "crypto"
    if is_german_equity(sym):
        return "xetra"
    return "us"


def venue_mark_returns(holdings: list[dict[str, Any]]) -> dict[str, Any]:
    """Cost-weighted since-buy mark % by listing venue (display only).

    xang1234 Group Matrix country/exchange cluster adapted as US RTH vs
    Xetra `.DE` vs crypto + cluster n. Complements equity/crypto sleeve.
    Missing mark → —. Not calendar 1w/1m; not a gate.
    """
    venues: dict[str, dict[str, Any]] = {
        "us": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "xetra": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "crypto": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
    }
    for h in holdings:
        if not isinstance(h, dict):
            continue
        basis = _holding_cost_basis(h)
        if basis <= 0:
            continue
        bucket = venues[_venue_bucket(h)]
        bucket["lots"] += 1
        pct = _holding_marked_pct(h)
        if pct is None:
            continue
        bucket["marked"] += 1
        bucket["cost"] += basis
        bucket["w_pct"] += basis * pct

    out: dict[str, Any] = {
        "venue_us_pct": None,
        "venue_xetra_pct": None,
        "venue_crypto_pct": None,
        "venue_us_label": "",
        "venue_xetra_label": "",
        "venue_crypto_label": "",
        "venue_us_lots": 0,
        "venue_xetra_lots": 0,
        "venue_crypto_lots": 0,
        "venue_marks_ready": False,
        "venue_marks_bit": "",
    }
    bits: list[str] = []
    for key, short, field in (
        ("us", "us", "venue_us"),
        ("xetra", "de", "venue_xetra"),
        ("crypto", "cr", "venue_crypto"),
    ):
        bucket = venues[key]
        has_lots = int(bucket["lots"]) > 0
        any_marked = int(bucket["marked"]) > 0
        pct: float | None = None
        if any_marked and float(bucket["cost"]) > 0:
            pct = float(bucket["w_pct"]) / float(bucket["cost"])
        cluster_n = int(bucket["marked"] if any_marked else bucket["lots"])
        label = _format_mark_pct(
            pct, has_lots=has_lots, any_marked=any_marked, cluster_n=cluster_n
        )
        out[f"{field}_lots"] = int(bucket["lots"])
        out[f"{field}_pct"] = round(pct, 2) if pct is not None else None
        out[f"{field}_label"] = label
        if label:
            bits.append(f"{short} {label}")
    if bits:
        out["venue_marks_ready"] = True
        out["venue_marks_bit"] = "venue " + " · ".join(bits)
    return out


def _exit_band_thresholds(h: dict[str, Any]) -> tuple[float, float]:
    """TP / SL % for this lot — stock asymmetric vs crypto ±10%."""
    from stock_checker.crypto_policy import (
        CRYPTO_STOP_LOSS_PCT,
        CRYPTO_TAKE_PROFIT_PCT,
    )
    from stock_checker.exit_policy import (
        DEFAULT_STOP_LOSS_PCT,
        DEFAULT_TAKE_PROFIT_PCT,
    )

    sym = str(h.get("symbol") or "")
    kind = str(h.get("kind") or "")
    if not kind:
        kind = "crypto" if is_crypto_symbol(sym) else "stock"
    if kind == "crypto" or is_crypto_symbol(sym):
        return CRYPTO_TAKE_PROFIT_PCT, CRYPTO_STOP_LOSS_PCT
    return DEFAULT_TAKE_PROFIT_PCT, DEFAULT_STOP_LOSS_PCT


def _exit_band_bucket(h: dict[str, Any]) -> str | None:
    """near-tp / mid / near-sl from since-buy mark vs live exit thresholds."""
    pct = _holding_marked_pct(h)
    if pct is None:
        return None
    tp, sl = _exit_band_thresholds(h)
    frac = float(EXIT_BAND_ZONE_FRAC)
    if frac <= 0:
        frac = 0.75
    if pct >= tp * frac:
        return "tp"
    if pct <= -(sl * frac):
        return "sl"
    return "mid"


def exit_band_mark_returns(holdings: list[dict[str, Any]]) -> dict[str, Any]:
    """Cost-weighted since-buy mark % by exit proximity (display only).

    xang1234 Group Matrix performance-band cluster adapted as near-TP /
    mid / near-SL using live stock TP+8%/SL−5% and crypto ±10% zones
    (75% of threshold). Unmarked do not dilute. Cluster n on labels.
    Strip only; not a gate; not calendar 1w/1m.
    """
    bands: dict[str, dict[str, Any]] = {
        "tp": {"cost": 0.0, "w_pct": 0.0, "lots": 0},
        "mid": {"cost": 0.0, "w_pct": 0.0, "lots": 0},
        "sl": {"cost": 0.0, "w_pct": 0.0, "lots": 0},
    }
    unmarked_lots = 0
    for h in holdings:
        if not isinstance(h, dict):
            continue
        basis = _holding_cost_basis(h)
        if basis <= 0:
            continue
        key = _exit_band_bucket(h)
        if key is None:
            unmarked_lots += 1
            continue
        pct = _holding_marked_pct(h)
        if pct is None:
            unmarked_lots += 1
            continue
        bucket = bands[key]
        bucket["lots"] += 1
        bucket["cost"] += basis
        bucket["w_pct"] += basis * pct

    out: dict[str, Any] = {
        "exit_band_tp_pct": None,
        "exit_band_mid_pct": None,
        "exit_band_sl_pct": None,
        "exit_band_tp_label": "",
        "exit_band_mid_label": "",
        "exit_band_sl_label": "",
        "exit_band_tp_lots": int(bands["tp"]["lots"]),
        "exit_band_mid_lots": int(bands["mid"]["lots"]),
        "exit_band_sl_lots": int(bands["sl"]["lots"]),
        "exit_band_unmarked_lots": unmarked_lots,
        "exit_band_marks_ready": False,
        "exit_band_marks_bit": "",
        "exit_band_zone_frac": float(EXIT_BAND_ZONE_FRAC),
    }
    bits: list[str] = []
    for key, short, field in (
        ("tp", "tp", "exit_band_tp"),
        ("mid", "mid", "exit_band_mid"),
        ("sl", "sl", "exit_band_sl"),
    ):
        bucket = bands[key]
        has_lots = int(bucket["lots"]) > 0
        pct: float | None = None
        if has_lots and float(bucket["cost"]) > 0:
            pct = float(bucket["w_pct"]) / float(bucket["cost"])
        n_lots = int(bucket["lots"])
        label = _format_mark_pct(
            pct, has_lots=has_lots, any_marked=has_lots, cluster_n=n_lots
        )
        out[f"{field}_pct"] = round(pct, 2) if pct is not None else None
        out[f"{field}_label"] = label
        if label:
            bits.append(f"{short} {label}")
    if bits:
        out["exit_band_marks_ready"] = True
        out["exit_band_marks_bit"] = "exit " + " · ".join(bits)
    return out


def _designed_rr(tp_pct: float, sl_pct: float) -> float | None:
    """Designed reward:risk at entry (TP magnitude / SL magnitude)."""
    try:
        tp = float(tp_pct)
        sl = float(sl_pct)
    except (TypeError, ValueError):
        return None
    if tp <= 0 or sl <= 0:
        return None
    return tp / sl


def _live_rr_bucket(h: dict[str, Any]) -> str | None:
    """ok / thin / hit from remaining reward:risk vs designed (latest mark).

    staskh rr_gate + RV-ratio rationale adapted: confirm against the current
    since-buy mark (not a forecast), and compare live remaining TP/SL distance
    to the designed entry ratio (stock 8:5 · crypto 1:1). ``hit`` when mark
    is already at/past a live band. Display only — not a gate.
    """
    pct = _holding_marked_pct(h)
    if pct is None:
        return None
    tp, sl = _exit_band_thresholds(h)
    designed = _designed_rr(tp, sl)
    if designed is None:
        return None
    if pct >= tp or pct <= -sl:
        return "hit"
    reward_left = tp - pct
    risk_left = pct + sl
    if reward_left <= 0 or risk_left <= 0:
        return "hit"
    live_rr = reward_left / risk_left
    if live_rr + 1e-12 >= designed:
        return "ok"
    return "thin"


def live_rr_mark_returns(holdings: list[dict[str, Any]]) -> dict[str, Any]:
    """Cost-weighted since-buy mark % by live remaining R:R (display only).

    staskh trading_skills rr_gate / RV-ratio docs adapted as Book Group
    Matrix: always state designed entry ratios (stock +8%/−5% → 1.6 · crypto
    ±10% → 1.0). When lots exist, cluster by remaining reward-to-TP vs
    risk-to-SL from latest marked % — ``ok`` (≥ designed), ``thin`` (inside
    bands but below designed), or ``hit`` (at/past live TP or SL). Unmarked →
    unknown. Cluster n on labels. Strip only; live exits stay ``exit_policy``;
    not a new gate — hard refuse-without-vol / rr entry block still deferred.
    """
    from stock_checker.crypto_policy import (
        CRYPTO_STOP_LOSS_PCT,
        CRYPTO_TAKE_PROFIT_PCT,
    )
    from stock_checker.exit_policy import (
        DEFAULT_STOP_LOSS_PCT,
        DEFAULT_TAKE_PROFIT_PCT,
    )

    stock_rr = _designed_rr(DEFAULT_TAKE_PROFIT_PCT, DEFAULT_STOP_LOSS_PCT)
    crypto_rr = _designed_rr(CRYPTO_TAKE_PROFIT_PCT, CRYPTO_STOP_LOSS_PCT)
    bands: dict[str, dict[str, Any]] = {
        "ok": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "thin": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "hit": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
    }
    unknown_lots = 0
    for h in holdings:
        if not isinstance(h, dict):
            continue
        basis = _holding_cost_basis(h)
        if basis <= 0:
            continue
        key = _live_rr_bucket(h)
        if key is None:
            unknown_lots += 1
            continue
        bucket = bands[key]
        bucket["lots"] += 1
        pct = _holding_marked_pct(h)
        if pct is None:
            continue
        bucket["marked"] += 1
        bucket["cost"] += basis
        bucket["w_pct"] += basis * pct

    stock_d = round(stock_rr, 2) if stock_rr is not None else None
    crypto_d = round(crypto_rr, 2) if crypto_rr is not None else None
    # staskh RV-ratio docs: always state what designed RR means (stock 8:5 → 1.6 ·
    # crypto 1:1 → 1.0), even when the book has no marked lots yet.
    if stock_d is not None and crypto_d is not None:
        designed_txt = f"{stock_d:g}/{crypto_d:g}"
    elif stock_d is not None:
        designed_txt = f"{stock_d:g}"
    elif crypto_d is not None:
        designed_txt = f"{crypto_d:g}"
    else:
        designed_txt = ""
    out: dict[str, Any] = {
        "live_rr_ok_pct": None,
        "live_rr_thin_pct": None,
        "live_rr_hit_pct": None,
        "live_rr_ok_label": "",
        "live_rr_thin_label": "",
        "live_rr_hit_label": "",
        "live_rr_ok_lots": 0,
        "live_rr_thin_lots": 0,
        "live_rr_hit_lots": 0,
        "live_rr_unknown_lots": unknown_lots,
        "live_rr_stock_designed": stock_d,
        "live_rr_crypto_designed": crypto_d,
        "live_rr_marks_ready": False,
        "live_rr_marks_bit": "",
    }
    bits: list[str] = []
    for key, short, field in (
        ("ok", "ok", "live_rr_ok"),
        ("thin", "thin", "live_rr_thin"),
        ("hit", "hit", "live_rr_hit"),
    ):
        bucket = bands[key]
        has_lots = int(bucket["lots"]) > 0
        any_marked = int(bucket["marked"]) > 0
        pct: float | None = None
        if any_marked and float(bucket["cost"]) > 0:
            pct = float(bucket["w_pct"]) / float(bucket["cost"])
        cluster_n = int(bucket["marked"] if any_marked else bucket["lots"])
        label = _format_mark_pct(
            pct, has_lots=has_lots, any_marked=any_marked, cluster_n=cluster_n
        )
        out[f"{field}_lots"] = int(bucket["lots"])
        out[f"{field}_pct"] = round(pct, 2) if pct is not None else None
        out[f"{field}_label"] = label
        if label:
            bits.append(f"{short} {label}")
    if bits and designed_txt:
        out["live_rr_marks_ready"] = True
        out["live_rr_marks_bit"] = f"rr {designed_txt} · " + " · ".join(bits)
    elif bits:
        out["live_rr_marks_ready"] = True
        out["live_rr_marks_bit"] = "rr " + " · ".join(bits)
    elif designed_txt:
        out["live_rr_marks_ready"] = True
        out["live_rr_marks_bit"] = f"rr designed {designed_txt}"
    return out


def _min_hold_lock_bucket(
    h: dict[str, Any],
    *,
    min_hold_seconds: float | None = None,
) -> str | None:
    """lock / free when hold age is known; None when age missing (A7)."""
    held_raw = h.get("held_seconds")
    if held_raw is None:
        return None
    try:
        held = float(held_raw)
    except (TypeError, ValueError):
        return None
    if held < 0:
        return None
    if "past_min_hold" in h:
        return "free" if bool(h.get("past_min_hold")) else "lock"
    if min_hold_seconds is None:
        return None
    try:
        need = max(0.0, float(min_hold_seconds))
    except (TypeError, ValueError):
        return None
    return "free" if held >= need else "lock"


def min_hold_mark_returns(
    holdings: list[dict[str, Any]],
    *,
    min_hold_seconds: float | None = None,
) -> dict[str, Any]:
    """Cost-weighted since-buy mark % by min-hold lock (display only).

    xang1234 Group Matrix + tradermonty lock cluster: lots still inside
    min-hold vs past unlock. Missing entry age → unknown (not lock).
    Cluster n on labels. Strip only; not a gate; not calendar 1w/1m.
    """
    bands: dict[str, dict[str, Any]] = {
        "lock": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "free": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
    }
    unknown_lots = 0
    for h in holdings:
        if not isinstance(h, dict):
            continue
        basis = _holding_cost_basis(h)
        if basis <= 0:
            continue
        key = _min_hold_lock_bucket(h, min_hold_seconds=min_hold_seconds)
        if key is None:
            unknown_lots += 1
            continue
        bucket = bands[key]
        bucket["lots"] += 1
        pct = _holding_marked_pct(h)
        if pct is None:
            continue
        bucket["marked"] += 1
        bucket["cost"] += basis
        bucket["w_pct"] += basis * pct

    out: dict[str, Any] = {
        "min_hold_lock_pct": None,
        "min_hold_free_pct": None,
        "min_hold_lock_label": "",
        "min_hold_free_label": "",
        "min_hold_lock_lots": 0,
        "min_hold_free_lots": 0,
        "min_hold_unknown_lots": unknown_lots,
        "min_hold_marks_ready": False,
        "min_hold_marks_bit": "",
    }
    bits: list[str] = []
    for key, short, field in (
        ("lock", "lock", "min_hold_lock"),
        ("free", "free", "min_hold_free"),
    ):
        bucket = bands[key]
        has_lots = int(bucket["lots"]) > 0
        any_marked = int(bucket["marked"]) > 0
        pct: float | None = None
        if any_marked and float(bucket["cost"]) > 0:
            pct = float(bucket["w_pct"]) / float(bucket["cost"])
        cluster_n = int(bucket["marked"] if any_marked else bucket["lots"])
        label = _format_mark_pct(
            pct, has_lots=has_lots, any_marked=any_marked, cluster_n=cluster_n
        )
        out[f"{field}_lots"] = int(bucket["lots"])
        out[f"{field}_pct"] = round(pct, 2) if pct is not None else None
        out[f"{field}_label"] = label
        if label:
            bits.append(f"{short} {label}")
    if bits:
        out["min_hold_marks_ready"] = True
        out["min_hold_marks_bit"] = "hold " + " · ".join(bits)
    return out


def _entry_session_bucket(h: dict[str, Any]) -> str | None:
    """wd = Mon–Fri UTC buy; we = Sat–Sun UTC; None if entry time missing."""
    raw = str(h.get("bought_at") or "").strip()
    if not raw:
        return None
    dt = _parse_trade_dt(raw)
    if dt is None:
        return None
    return "we" if dt.weekday() >= 5 else "wd"


def entry_session_mark_returns(
    holdings: list[dict[str, Any]],
) -> dict[str, Any]:
    """Cost-weighted since-buy mark % by entry weekday session (display only).

    xang1234 session + portfolio AI Group Matrix: lots bought Mon–Fri UTC
    (wd) vs Sat–Sun UTC (we). Weekend entries are normally crypto-only
    (stocks pause). Missing ``bought_at`` → unknown (not weekday). Cluster
    n on labels. Strip only; not a gate; not calendar 1w/1m.
    """
    bands: dict[str, dict[str, Any]] = {
        "wd": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "we": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
    }
    unknown_lots = 0
    for h in holdings:
        if not isinstance(h, dict):
            continue
        basis = _holding_cost_basis(h)
        if basis <= 0:
            continue
        key = _entry_session_bucket(h)
        if key is None:
            unknown_lots += 1
            continue
        bucket = bands[key]
        bucket["lots"] += 1
        pct = _holding_marked_pct(h)
        if pct is None:
            continue
        bucket["marked"] += 1
        bucket["cost"] += basis
        bucket["w_pct"] += basis * pct

    out: dict[str, Any] = {
        "entry_session_wd_pct": None,
        "entry_session_we_pct": None,
        "entry_session_wd_label": "",
        "entry_session_we_label": "",
        "entry_session_wd_lots": 0,
        "entry_session_we_lots": 0,
        "entry_session_unknown_lots": unknown_lots,
        "entry_session_marks_ready": False,
        "entry_session_marks_bit": "",
    }
    bits: list[str] = []
    for key, short, field in (
        ("wd", "wd", "entry_session_wd"),
        ("we", "we", "entry_session_we"),
    ):
        bucket = bands[key]
        has_lots = int(bucket["lots"]) > 0
        any_marked = int(bucket["marked"]) > 0
        pct: float | None = None
        if any_marked and float(bucket["cost"]) > 0:
            pct = float(bucket["w_pct"]) / float(bucket["cost"])
        cluster_n = int(bucket["marked"] if any_marked else bucket["lots"])
        label = _format_mark_pct(
            pct, has_lots=has_lots, any_marked=any_marked, cluster_n=cluster_n
        )
        out[f"{field}_lots"] = int(bucket["lots"])
        out[f"{field}_pct"] = round(pct, 2) if pct is not None else None
        out[f"{field}_label"] = label
        if label:
            bits.append(f"{short} {label}")
    if bits:
        out["entry_session_marks_ready"] = True
        out["entry_session_marks_bit"] = "session " + " · ".join(bits)
    return out



def _entry_hours_bucket(h: dict[str, Any]) -> str | None:
    """open = equity cash session; closed = AH/weekend equity; cr = crypto.

    None if equity entry time missing/unparseable.
    """
    sym = str(h.get("symbol") or "").strip()
    if not sym:
        return None
    if is_crypto_symbol(sym) or str(h.get("kind") or "").lower() == "crypto":
        return "cr"
    raw = str(h.get("bought_at") or "").strip()
    if not raw:
        return None
    dt = _parse_trade_dt(raw)
    if dt is None:
        return None
    return "closed" if is_equity_session_closed(sym, now=dt) else "open"


def entry_hours_mark_returns(
    holdings: list[dict[str, Any]],
) -> dict[str, Any]:
    """Cost-weighted since-buy mark % by entry cash-session hours (display only).

    xang1234 equity-hours + RyanJHamby daily-scan honesty + portfolio AI
    Group Matrix: lots bought in US RTH / Xetra open vs outside cash hours
    (AH/premarket/weekend equity) vs crypto 24/7. Missing ``bought_at`` on
    equities → unknown (not open). Cluster n on labels. Strip only; not a
    gate; not calendar 1w/1m.
    """
    bands: dict[str, dict[str, Any]] = {
        "open": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "closed": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "cr": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
    }
    unknown_lots = 0
    for h in holdings:
        if not isinstance(h, dict):
            continue
        basis = _holding_cost_basis(h)
        if basis <= 0:
            continue
        key = _entry_hours_bucket(h)
        if key is None:
            unknown_lots += 1
            continue
        bucket = bands[key]
        bucket["lots"] += 1
        pct = _holding_marked_pct(h)
        if pct is None:
            continue
        bucket["marked"] += 1
        bucket["cost"] += basis
        bucket["w_pct"] += basis * pct

    out: dict[str, Any] = {
        "entry_hours_open_pct": None,
        "entry_hours_closed_pct": None,
        "entry_hours_cr_pct": None,
        "entry_hours_open_label": "",
        "entry_hours_closed_label": "",
        "entry_hours_cr_label": "",
        "entry_hours_open_lots": 0,
        "entry_hours_closed_lots": 0,
        "entry_hours_cr_lots": 0,
        "entry_hours_unknown_lots": unknown_lots,
        "entry_hours_marks_ready": False,
        "entry_hours_marks_bit": "",
    }
    bits: list[str] = []
    for key, short, field in (
        ("open", "open", "entry_hours_open"),
        ("closed", "closed", "entry_hours_closed"),
        ("cr", "cr", "entry_hours_cr"),
    ):
        bucket = bands[key]
        has_lots = int(bucket["lots"]) > 0
        any_marked = int(bucket["marked"]) > 0
        pct: float | None = None
        if any_marked and float(bucket["cost"]) > 0:
            pct = float(bucket["w_pct"]) / float(bucket["cost"])
        cluster_n = int(bucket["marked"] if any_marked else bucket["lots"])
        label = _format_mark_pct(
            pct, has_lots=has_lots, any_marked=any_marked, cluster_n=cluster_n
        )
        out[f"{field}_lots"] = int(bucket["lots"])
        out[f"{field}_pct"] = round(pct, 2) if pct is not None else None
        out[f"{field}_label"] = label
        if label:
            bits.append(f"{short} {label}")
    if bits:
        out["entry_hours_marks_ready"] = True
        out["entry_hours_marks_bit"] = "hours " + " · ".join(bits)
    return out


def _sell_epochs_by_symbol(
    trades: Iterable[Mapping[str, Any]] | None,
) -> dict[str, list[float]]:
    """Symbol → sorted sell epochs from trades.jsonl rows (display only)."""
    out: dict[str, list[float]] = {}
    if not trades:
        return out
    for raw in trades:
        if not isinstance(raw, Mapping):
            continue
        if str(raw.get("type") or "").upper() != "SELL":
            continue
        sym = str(raw.get("symbol") or "").strip().upper()
        if not sym:
            continue
        epoch = _parse_trade_epoch(str(raw.get("timestamp") or ""))
        if epoch is None:
            continue
        out.setdefault(sym, []).append(float(epoch))
    for sym, epochs in out.items():
        epochs.sort()
    return out


def _entry_rebuy_bucket(
    h: dict[str, Any],
    sell_epochs: dict[str, list[float]],
) -> str | None:
    """rebuy = prior SELL before buy; fresh = no prior SELL; None if no entry time."""
    sym = str(h.get("symbol") or "").strip().upper()
    if not sym:
        return None
    raw = str(h.get("bought_at") or "").strip()
    if not raw:
        return None
    buy_epoch = _parse_trade_epoch(raw)
    if buy_epoch is None:
        return None
    for sell_epoch in sell_epochs.get(sym) or []:
        if sell_epoch < buy_epoch:
            return "rebuy"
        # sells sorted ascending — later timestamps cannot be prior
        break
    return "fresh"


def entry_rebuy_mark_returns(
    holdings: list[dict[str, Any]],
    trades: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Cost-weighted since-buy mark % by rebuy vs fresh entry (display only).

    tradermonty flip-flop / SCHW honesty + portfolio AI Group Matrix: lots
    whose symbol had a SELL in ``trades`` before ``bought_at`` (rebuy) vs no
    prior exit (fresh). Missing ``bought_at`` → unknown. Empty ledger → all
    dated lots count as fresh (no evidence of prior exit). Cluster n on
    labels. Strip only; not a gate; not calendar 1w/1m.
    """
    sells = _sell_epochs_by_symbol(trades)
    bands: dict[str, dict[str, Any]] = {
        "rebuy": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "fresh": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
    }
    unknown_lots = 0
    for h in holdings:
        if not isinstance(h, dict):
            continue
        basis = _holding_cost_basis(h)
        if basis <= 0:
            continue
        key = _entry_rebuy_bucket(h, sells)
        if key is None:
            unknown_lots += 1
            continue
        bucket = bands[key]
        bucket["lots"] += 1
        pct = _holding_marked_pct(h)
        if pct is None:
            continue
        bucket["marked"] += 1
        bucket["cost"] += basis
        bucket["w_pct"] += basis * pct

    out: dict[str, Any] = {
        "entry_rebuy_rebuy_pct": None,
        "entry_rebuy_fresh_pct": None,
        "entry_rebuy_rebuy_label": "",
        "entry_rebuy_fresh_label": "",
        "entry_rebuy_rebuy_lots": 0,
        "entry_rebuy_fresh_lots": 0,
        "entry_rebuy_unknown_lots": unknown_lots,
        "entry_rebuy_marks_ready": False,
        "entry_rebuy_marks_bit": "",
    }
    bits: list[str] = []
    for key, short, field in (
        ("rebuy", "rebuy", "entry_rebuy_rebuy"),
        ("fresh", "fresh", "entry_rebuy_fresh"),
    ):
        bucket = bands[key]
        has_lots = int(bucket["lots"]) > 0
        any_marked = int(bucket["marked"]) > 0
        pct: float | None = None
        if any_marked and float(bucket["cost"]) > 0:
            pct = float(bucket["w_pct"]) / float(bucket["cost"])
        cluster_n = int(bucket["marked"] if any_marked else bucket["lots"])
        label = _format_mark_pct(
            pct, has_lots=has_lots, any_marked=any_marked, cluster_n=cluster_n
        )
        out[f"{field}_lots"] = int(bucket["lots"])
        out[f"{field}_pct"] = round(pct, 2) if pct is not None else None
        out[f"{field}_label"] = label
        if label:
            bits.append(f"{short} {label}")
    if bits:
        out["entry_rebuy_marks_ready"] = True
        out["entry_rebuy_marks_bit"] = "rebuy " + " · ".join(bits)
    return out


def _prior_sell_epoch_before_buy(
    h: dict[str, Any],
    sell_epochs: dict[str, list[float]],
) -> tuple[float | None, float | None]:
    """(buy_epoch, most recent prior sell epoch) or (None, None) if no buy time."""
    sym = str(h.get("symbol") or "").strip().upper()
    if not sym:
        return None, None
    raw = str(h.get("bought_at") or "").strip()
    if not raw:
        return None, None
    buy_epoch = _parse_trade_epoch(raw)
    if buy_epoch is None:
        return None, None
    prior: float | None = None
    for sell_epoch in sell_epochs.get(sym) or []:
        if sell_epoch < buy_epoch:
            prior = float(sell_epoch)
        else:
            break
    return float(buy_epoch), prior


def _entry_rebuy_gap_bucket(
    h: dict[str, Any],
    sell_epochs: dict[str, list[float]],
    *,
    cooldown_seconds: float,
) -> str | None:
    """fast / cool / fresh from gap to prior SELL; None if no entry time."""
    buy_epoch, prior = _prior_sell_epoch_before_buy(h, sell_epochs)
    if buy_epoch is None:
        return None
    if prior is None:
        return "fresh"
    gap = buy_epoch - prior
    need = max(0.0, float(cooldown_seconds))
    if gap < need:
        return "fast"
    return "cool"


def entry_rebuy_gap_mark_returns(
    holdings: list[dict[str, Any]],
    trades: Iterable[Mapping[str, Any]] | None = None,
    *,
    cooldown_seconds: float | None = None,
) -> dict[str, Any]:
    """Cost-weighted since-buy mark % by rebuy cooldown gap (display only).

    tradermonty SCHW flip-flop + portfolio AI Group Matrix twin of Rebuy:
    lots whose most recent prior SELL was inside the anti-rebuy cooldown
    (``fast``) vs after cooldown (``cool``) vs no prior SELL (``fresh``).
    Default cooldown matches Ops min hold (24h). Missing ``bought_at`` →
    unknown. Empty ledger → all dated lots count as fresh. Cluster n on
    labels. Strip only; not a gate — live ``should_allow_rebuy`` still
    blocks fast rebeys.
    """
    try:
        cool = (
            float(DEFAULT_REBUY_COOLDOWN_SEC)
            if cooldown_seconds is None
            else max(0.0, float(cooldown_seconds))
        )
    except (TypeError, ValueError):
        cool = float(DEFAULT_REBUY_COOLDOWN_SEC)
    sells = _sell_epochs_by_symbol(trades)
    bands: dict[str, dict[str, Any]] = {
        "fast": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "cool": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "fresh": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
    }
    unknown_lots = 0
    for h in holdings:
        if not isinstance(h, dict):
            continue
        basis = _holding_cost_basis(h)
        if basis <= 0:
            continue
        key = _entry_rebuy_gap_bucket(h, sells, cooldown_seconds=cool)
        if key is None:
            unknown_lots += 1
            continue
        bucket = bands[key]
        bucket["lots"] += 1
        pct = _holding_marked_pct(h)
        if pct is None:
            continue
        bucket["marked"] += 1
        bucket["cost"] += basis
        bucket["w_pct"] += basis * pct

    out: dict[str, Any] = {
        "entry_rebuy_gap_fast_pct": None,
        "entry_rebuy_gap_cool_pct": None,
        "entry_rebuy_gap_fresh_pct": None,
        "entry_rebuy_gap_fast_label": "",
        "entry_rebuy_gap_cool_label": "",
        "entry_rebuy_gap_fresh_label": "",
        "entry_rebuy_gap_fast_lots": 0,
        "entry_rebuy_gap_cool_lots": 0,
        "entry_rebuy_gap_fresh_lots": 0,
        "entry_rebuy_gap_unknown_lots": unknown_lots,
        "entry_rebuy_gap_marks_ready": False,
        "entry_rebuy_gap_marks_bit": "",
        "entry_rebuy_gap_cooldown_sec": cool,
    }
    bits: list[str] = []
    for key, short, field in (
        ("fast", "fast", "entry_rebuy_gap_fast"),
        ("cool", "cool", "entry_rebuy_gap_cool"),
        ("fresh", "fresh", "entry_rebuy_gap_fresh"),
    ):
        bucket = bands[key]
        has_lots = int(bucket["lots"]) > 0
        any_marked = int(bucket["marked"]) > 0
        pct: float | None = None
        if any_marked and float(bucket["cost"]) > 0:
            pct = float(bucket["w_pct"]) / float(bucket["cost"])
        cluster_n = int(bucket["marked"] if any_marked else bucket["lots"])
        label = _format_mark_pct(
            pct, has_lots=has_lots, any_marked=any_marked, cluster_n=cluster_n
        )
        out[f"{field}_lots"] = int(bucket["lots"])
        out[f"{field}_pct"] = round(pct, 2) if pct is not None else None
        out[f"{field}_label"] = label
        if label:
            bits.append(f"{short} {label}")
    if bits:
        out["entry_rebuy_gap_marks_ready"] = True
        out["entry_rebuy_gap_marks_bit"] = "gap " + " · ".join(bits)
    return out


def _sell_events_by_symbol(
    trades: Iterable[Mapping[str, Any]] | None,
) -> dict[str, list[tuple[float, str]]]:
    """Symbol → sorted (epoch, exit_reason) SELL events (display only)."""
    out: dict[str, list[tuple[float, str]]] = {}
    if not trades:
        return out
    for raw in trades:
        if not isinstance(raw, Mapping):
            continue
        if str(raw.get("type") or "").upper() != "SELL":
            continue
        sym = str(raw.get("symbol") or "").strip().upper()
        if not sym:
            continue
        epoch = _parse_trade_epoch(str(raw.get("timestamp") or ""))
        if epoch is None:
            continue
        reason = str(raw.get("exit_reason") or "").strip().lower()
        out.setdefault(sym, []).append((float(epoch), reason))
    for sym, events in out.items():
        events.sort(key=lambda item: item[0])
    return out


def _entry_post_sl_bucket(
    h: dict[str, Any],
    sell_events: dict[str, list[tuple[float, str]]],
) -> str | None:
    """sl / oth / fresh from most recent prior SELL; None if no entry time."""
    sym = str(h.get("symbol") or "").strip().upper()
    if not sym:
        return None
    raw = str(h.get("bought_at") or "").strip()
    if not raw:
        return None
    buy_epoch = _parse_trade_epoch(raw)
    if buy_epoch is None:
        return None
    prior: tuple[float, str] | None = None
    for epoch, reason in sell_events.get(sym) or []:
        if epoch < buy_epoch:
            prior = (epoch, reason)
            continue
        break
    if prior is None:
        return "fresh"
    if prior[1] == "sl":
        return "sl"
    return "oth"


def entry_post_sl_mark_returns(
    holdings: list[dict[str, Any]],
    trades: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Cost-weighted since-buy mark % by post-SL refill vs other (display only).

    tradermonty anti revenge-refill + portfolio AI Group Matrix: lots whose
    most recent prior SELL of the same symbol had ``exit_reason=sl`` (sl) vs
    any other prior exit (oth) vs no prior SELL (fresh). Missing
    ``bought_at`` → unknown. Empty ledger → all dated lots count as fresh.
    Cluster n on labels. Strip only; not a gate; pairs with rebuy cluster.
    """
    sells = _sell_events_by_symbol(trades)
    bands: dict[str, dict[str, Any]] = {
        "sl": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "oth": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "fresh": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
    }
    unknown_lots = 0
    for h in holdings:
        if not isinstance(h, dict):
            continue
        basis = _holding_cost_basis(h)
        if basis <= 0:
            continue
        key = _entry_post_sl_bucket(h, sells)
        if key is None:
            unknown_lots += 1
            continue
        bucket = bands[key]
        bucket["lots"] += 1
        pct = _holding_marked_pct(h)
        if pct is None:
            continue
        bucket["marked"] += 1
        bucket["cost"] += basis
        bucket["w_pct"] += basis * pct

    out: dict[str, Any] = {
        "entry_post_sl_sl_pct": None,
        "entry_post_sl_oth_pct": None,
        "entry_post_sl_fresh_pct": None,
        "entry_post_sl_sl_label": "",
        "entry_post_sl_oth_label": "",
        "entry_post_sl_fresh_label": "",
        "entry_post_sl_sl_lots": 0,
        "entry_post_sl_oth_lots": 0,
        "entry_post_sl_fresh_lots": 0,
        "entry_post_sl_unknown_lots": unknown_lots,
        "entry_post_sl_marks_ready": False,
        "entry_post_sl_marks_bit": "",
    }
    bits: list[str] = []
    for key, short, field in (
        ("sl", "sl", "entry_post_sl_sl"),
        ("oth", "oth", "entry_post_sl_oth"),
        ("fresh", "fresh", "entry_post_sl_fresh"),
    ):
        bucket = bands[key]
        has_lots = int(bucket["lots"]) > 0
        any_marked = int(bucket["marked"]) > 0
        pct: float | None = None
        if any_marked and float(bucket["cost"]) > 0:
            pct = float(bucket["w_pct"]) / float(bucket["cost"])
        cluster_n = int(bucket["marked"] if any_marked else bucket["lots"])
        label = _format_mark_pct(
            pct, has_lots=has_lots, any_marked=any_marked, cluster_n=cluster_n
        )
        out[f"{field}_lots"] = int(bucket["lots"])
        out[f"{field}_pct"] = round(pct, 2) if pct is not None else None
        out[f"{field}_label"] = label
        if label:
            bits.append(f"{short} {label}")
    if bits:
        out["entry_post_sl_marks_ready"] = True
        out["entry_post_sl_marks_bit"] = "post-sl " + " · ".join(bits)
    return out


def _entry_post_tp_bucket(
    h: dict[str, Any],
    sell_events: dict[str, list[tuple[float, str]]],
) -> str | None:
    """tp / oth / fresh from most recent prior SELL; None if no entry time."""
    sym = str(h.get("symbol") or "").strip().upper()
    if not sym:
        return None
    raw = str(h.get("bought_at") or "").strip()
    if not raw:
        return None
    buy_epoch = _parse_trade_epoch(raw)
    if buy_epoch is None:
        return None
    prior: tuple[float, str] | None = None
    for epoch, reason in sell_events.get(sym) or []:
        if epoch < buy_epoch:
            prior = (epoch, reason)
            continue
        break
    if prior is None:
        return "fresh"
    if prior[1] == "tp":
        return "tp"
    return "oth"


def entry_post_tp_mark_returns(
    holdings: list[dict[str, Any]],
    trades: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Cost-weighted since-buy mark % by post-TP refill vs other (display only).

    tradermonty + portfolio AI Group Matrix twin of post-SL: lots whose most
    recent prior SELL of the same symbol had ``exit_reason=tp`` (tp) vs any
    other prior exit (oth) vs no prior SELL (fresh). Missing ``bought_at`` →
    unknown. Empty ledger → all dated lots count as fresh. Cluster n on
    labels. Strip only; not a gate; anti chase-refill after take-profit.
    """
    sells = _sell_events_by_symbol(trades)
    bands: dict[str, dict[str, Any]] = {
        "tp": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "oth": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "fresh": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
    }
    unknown_lots = 0
    for h in holdings:
        if not isinstance(h, dict):
            continue
        basis = _holding_cost_basis(h)
        if basis <= 0:
            continue
        key = _entry_post_tp_bucket(h, sells)
        if key is None:
            unknown_lots += 1
            continue
        bucket = bands[key]
        bucket["lots"] += 1
        pct = _holding_marked_pct(h)
        if pct is None:
            continue
        bucket["marked"] += 1
        bucket["cost"] += basis
        bucket["w_pct"] += basis * pct

    out: dict[str, Any] = {
        "entry_post_tp_tp_pct": None,
        "entry_post_tp_oth_pct": None,
        "entry_post_tp_fresh_pct": None,
        "entry_post_tp_tp_label": "",
        "entry_post_tp_oth_label": "",
        "entry_post_tp_fresh_label": "",
        "entry_post_tp_tp_lots": 0,
        "entry_post_tp_oth_lots": 0,
        "entry_post_tp_fresh_lots": 0,
        "entry_post_tp_unknown_lots": unknown_lots,
        "entry_post_tp_marks_ready": False,
        "entry_post_tp_marks_bit": "",
    }
    bits: list[str] = []
    for key, short, field in (
        ("tp", "tp", "entry_post_tp_tp"),
        ("oth", "oth", "entry_post_tp_oth"),
        ("fresh", "fresh", "entry_post_tp_fresh"),
    ):
        bucket = bands[key]
        has_lots = int(bucket["lots"]) > 0
        any_marked = int(bucket["marked"]) > 0
        pct: float | None = None
        if any_marked and float(bucket["cost"]) > 0:
            pct = float(bucket["w_pct"]) / float(bucket["cost"])
        cluster_n = int(bucket["marked"] if any_marked else bucket["lots"])
        label = _format_mark_pct(
            pct, has_lots=has_lots, any_marked=any_marked, cluster_n=cluster_n
        )
        out[f"{field}_lots"] = int(bucket["lots"])
        out[f"{field}_pct"] = round(pct, 2) if pct is not None else None
        out[f"{field}_label"] = label
        if label:
            bits.append(f"{short} {label}")
    if bits:
        out["entry_post_tp_marks_ready"] = True
        out["entry_post_tp_marks_bit"] = "post-tp " + " · ".join(bits)
    return out


def _entry_post_rotation_bucket(
    h: dict[str, Any],
    sell_events: dict[str, list[tuple[float, str]]],
) -> str | None:
    """rot / oth / fresh from most recent prior SELL; None if no entry time."""
    sym = str(h.get("symbol") or "").strip().upper()
    if not sym:
        return None
    raw = str(h.get("bought_at") or "").strip()
    if not raw:
        return None
    buy_epoch = _parse_trade_epoch(raw)
    if buy_epoch is None:
        return None
    prior: tuple[float, str] | None = None
    for epoch, reason in sell_events.get(sym) or []:
        if epoch < buy_epoch:
            prior = (epoch, reason)
            continue
        break
    if prior is None:
        return "fresh"
    if prior[1] == "rotation":
        return "rot"
    return "oth"


def entry_post_rotation_mark_returns(
    holdings: list[dict[str, Any]],
    trades: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Cost-weighted since-buy mark % by post-rotation refill vs other (display only).

    tradermonty + xang1234 stale-rotation + portfolio AI Group Matrix twin of
    post-SL/post-TP: lots whose most recent prior SELL of the same symbol had
    ``exit_reason=rotation`` (rot) vs any other prior exit (oth) vs no prior
    SELL (fresh). Missing ``bought_at`` → unknown. Empty ledger → all dated
    lots count as fresh. Cluster n on labels. Strip only; not a gate; SCHW
    scan-chase refill honesty.
    """
    sells = _sell_events_by_symbol(trades)
    bands: dict[str, dict[str, Any]] = {
        "rot": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "oth": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "fresh": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
    }
    unknown_lots = 0
    for h in holdings:
        if not isinstance(h, dict):
            continue
        basis = _holding_cost_basis(h)
        if basis <= 0:
            continue
        key = _entry_post_rotation_bucket(h, sells)
        if key is None:
            unknown_lots += 1
            continue
        bucket = bands[key]
        bucket["lots"] += 1
        pct = _holding_marked_pct(h)
        if pct is None:
            continue
        bucket["marked"] += 1
        bucket["cost"] += basis
        bucket["w_pct"] += basis * pct

    out: dict[str, Any] = {
        "entry_post_rot_rot_pct": None,
        "entry_post_rot_oth_pct": None,
        "entry_post_rot_fresh_pct": None,
        "entry_post_rot_rot_label": "",
        "entry_post_rot_oth_label": "",
        "entry_post_rot_fresh_label": "",
        "entry_post_rot_rot_lots": 0,
        "entry_post_rot_oth_lots": 0,
        "entry_post_rot_fresh_lots": 0,
        "entry_post_rot_unknown_lots": unknown_lots,
        "entry_post_rot_marks_ready": False,
        "entry_post_rot_marks_bit": "",
    }
    bits: list[str] = []
    for key, short, field in (
        ("rot", "rot", "entry_post_rot_rot"),
        ("oth", "oth", "entry_post_rot_oth"),
        ("fresh", "fresh", "entry_post_rot_fresh"),
    ):
        bucket = bands[key]
        has_lots = int(bucket["lots"]) > 0
        any_marked = int(bucket["marked"]) > 0
        pct: float | None = None
        if any_marked and float(bucket["cost"]) > 0:
            pct = float(bucket["w_pct"]) / float(bucket["cost"])
        cluster_n = int(bucket["marked"] if any_marked else bucket["lots"])
        label = _format_mark_pct(
            pct, has_lots=has_lots, any_marked=any_marked, cluster_n=cluster_n
        )
        out[f"{field}_lots"] = int(bucket["lots"])
        out[f"{field}_pct"] = round(pct, 2) if pct is not None else None
        out[f"{field}_label"] = label
        if label:
            bits.append(f"{short} {label}")
    if bits:
        out["entry_post_rot_marks_ready"] = True
        out["entry_post_rot_marks_bit"] = "post-rot " + " · ".join(bits)
    return out


def _entry_post_trim_bucket(
    h: dict[str, Any],
    sell_events: dict[str, list[tuple[float, str]]],
) -> str | None:
    """trim / oth / fresh from most recent prior SELL; None if no entry time."""
    sym = str(h.get("symbol") or "").strip().upper()
    if not sym:
        return None
    raw = str(h.get("bought_at") or "").strip()
    if not raw:
        return None
    buy_epoch = _parse_trade_epoch(raw)
    if buy_epoch is None:
        return None
    prior: tuple[float, str] | None = None
    for epoch, reason in sell_events.get(sym) or []:
        if epoch < buy_epoch:
            prior = (epoch, reason)
            continue
        break
    if prior is None:
        return "fresh"
    if prior[1] == "trim":
        return "trim"
    return "oth"


def entry_post_trim_mark_returns(
    holdings: list[dict[str, Any]],
    trades: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Cost-weighted since-buy mark % by post-trim refill vs other (display only).

    tradermonty + staskh overweight-trim + portfolio AI Group Matrix twin of
    post-SL/post-TP/post-rot: lots whose most recent prior SELL of the same
    symbol had ``exit_reason=trim`` (trim) vs any other prior exit (oth) vs
    no prior SELL (fresh). Missing ``bought_at`` → unknown. Empty ledger →
    all dated lots count as fresh. Cluster n on labels. Strip only; not a
    gate; A16 trim-to-cap refill honesty.
    """
    sells = _sell_events_by_symbol(trades)
    bands: dict[str, dict[str, Any]] = {
        "trim": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "oth": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "fresh": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
    }
    unknown_lots = 0
    for h in holdings:
        if not isinstance(h, dict):
            continue
        basis = _holding_cost_basis(h)
        if basis <= 0:
            continue
        key = _entry_post_trim_bucket(h, sells)
        if key is None:
            unknown_lots += 1
            continue
        bucket = bands[key]
        bucket["lots"] += 1
        pct = _holding_marked_pct(h)
        if pct is None:
            continue
        bucket["marked"] += 1
        bucket["cost"] += basis
        bucket["w_pct"] += basis * pct

    out: dict[str, Any] = {
        "entry_post_trim_trim_pct": None,
        "entry_post_trim_oth_pct": None,
        "entry_post_trim_fresh_pct": None,
        "entry_post_trim_trim_label": "",
        "entry_post_trim_oth_label": "",
        "entry_post_trim_fresh_label": "",
        "entry_post_trim_trim_lots": 0,
        "entry_post_trim_oth_lots": 0,
        "entry_post_trim_fresh_lots": 0,
        "entry_post_trim_unknown_lots": unknown_lots,
        "entry_post_trim_marks_ready": False,
        "entry_post_trim_marks_bit": "",
    }
    bits: list[str] = []
    for key, short, field in (
        ("trim", "trim", "entry_post_trim_trim"),
        ("oth", "oth", "entry_post_trim_oth"),
        ("fresh", "fresh", "entry_post_trim_fresh"),
    ):
        bucket = bands[key]
        has_lots = int(bucket["lots"]) > 0
        any_marked = int(bucket["marked"]) > 0
        pct: float | None = None
        if any_marked and float(bucket["cost"]) > 0:
            pct = float(bucket["w_pct"]) / float(bucket["cost"])
        cluster_n = int(bucket["marked"] if any_marked else bucket["lots"])
        label = _format_mark_pct(
            pct, has_lots=has_lots, any_marked=any_marked, cluster_n=cluster_n
        )
        out[f"{field}_lots"] = int(bucket["lots"])
        out[f"{field}_pct"] = round(pct, 2) if pct is not None else None
        out[f"{field}_label"] = label
        if label:
            bits.append(f"{short} {label}")
    if bits:
        out["entry_post_trim_marks_ready"] = True
        out["entry_post_trim_marks_bit"] = "post-trim " + " · ".join(bits)
    return out


def _buy_fee_events_by_symbol(
    trades: Iterable[Mapping[str, Any]] | None,
) -> dict[str, list[tuple[float, float]]]:
    """Symbol → sorted (epoch, commission) BUY events (display only)."""
    out: dict[str, list[tuple[float, float]]] = {}
    if not trades:
        return out
    for raw in trades:
        if not isinstance(raw, Mapping):
            continue
        if str(raw.get("type") or "").upper() != "BUY":
            continue
        sym = str(raw.get("symbol") or "").strip().upper()
        if not sym:
            continue
        epoch = _parse_trade_epoch(str(raw.get("timestamp") or ""))
        if epoch is None:
            continue
        if "commission" not in raw:
            continue
        try:
            fee = float(raw.get("commission") or 0.0)
        except (TypeError, ValueError):
            continue
        out.setdefault(sym, []).append((float(epoch), fee))
    for sym, events in out.items():
        events.sort(key=lambda item: item[0])
    return out


def _entry_buy_fee_bucket(
    h: dict[str, Any],
    buy_events: dict[str, list[tuple[float, float]]],
) -> str | None:
    """free / paid from matching BUY commission; None if no entry or fee row."""
    sym = str(h.get("symbol") or "").strip().upper()
    if not sym:
        return None
    raw = str(h.get("bought_at") or "").strip()
    if not raw:
        return None
    buy_epoch = _parse_trade_epoch(raw)
    if buy_epoch is None:
        return None
    # Exact timestamp match (portfolio bought_at == BUY timestamp).
    for epoch, fee in buy_events.get(sym) or []:
        if abs(epoch - buy_epoch) < 0.5:
            return "free" if fee <= 0.0 else "paid"
    return None


def entry_buy_fee_mark_returns(
    holdings: list[dict[str, Any]],
    trades: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Cost-weighted since-buy mark % by buy-leg fee (display only).

    portfolio AI + Revolut allowance honesty + Group Matrix: lots whose
    matching BUY ``commission`` was €0 (free monthly leg) vs paid (>0).
    Missing ``bought_at`` / no matching BUY fee row → unknown. Cluster n on
    labels. Strip only; not a gate; crypto fees still not modeled on live
    policy — this mirrors ledger commissions only.
    """
    buys = _buy_fee_events_by_symbol(trades)
    bands: dict[str, dict[str, Any]] = {
        "free": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "paid": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
    }
    unknown_lots = 0
    for h in holdings:
        if not isinstance(h, dict):
            continue
        basis = _holding_cost_basis(h)
        if basis <= 0:
            continue
        key = _entry_buy_fee_bucket(h, buys)
        if key is None:
            unknown_lots += 1
            continue
        bucket = bands[key]
        bucket["lots"] += 1
        pct = _holding_marked_pct(h)
        if pct is None:
            continue
        bucket["marked"] += 1
        bucket["cost"] += basis
        bucket["w_pct"] += basis * pct

    out: dict[str, Any] = {
        "entry_buy_fee_free_pct": None,
        "entry_buy_fee_paid_pct": None,
        "entry_buy_fee_free_label": "",
        "entry_buy_fee_paid_label": "",
        "entry_buy_fee_free_lots": 0,
        "entry_buy_fee_paid_lots": 0,
        "entry_buy_fee_unknown_lots": unknown_lots,
        "entry_buy_fee_marks_ready": False,
        "entry_buy_fee_marks_bit": "",
    }
    bits: list[str] = []
    for key, short, field in (
        ("free", "free", "entry_buy_fee_free"),
        ("paid", "paid", "entry_buy_fee_paid"),
    ):
        bucket = bands[key]
        has_lots = int(bucket["lots"]) > 0
        any_marked = int(bucket["marked"]) > 0
        pct: float | None = None
        if any_marked and float(bucket["cost"]) > 0:
            pct = float(bucket["w_pct"]) / float(bucket["cost"])
        cluster_n = int(bucket["marked"] if any_marked else bucket["lots"])
        label = _format_mark_pct(
            pct, has_lots=has_lots, any_marked=any_marked, cluster_n=cluster_n
        )
        out[f"{field}_lots"] = int(bucket["lots"])
        out[f"{field}_pct"] = round(pct, 2) if pct is not None else None
        out[f"{field}_label"] = label
        if label:
            bits.append(f"{short} {label}")
    if bits:
        out["entry_buy_fee_marks_ready"] = True
        out["entry_buy_fee_marks_bit"] = "fee " + " · ".join(bits)
    return out


def _normalize_buy_confidence(raw: Any) -> str:
    """Map ledger confidence to hi / med / lo / none (display only)."""
    conf = str(raw or "").strip().upper()
    if conf == "MEDIUM":
        conf = "MED"
    if conf == "HIGH":
        return "hi"
    if conf == "MED":
        return "med"
    if conf == "LOW":
        return "lo"
    return "none"


def _buy_confidence_events_by_symbol(
    trades: Iterable[Mapping[str, Any]] | None,
) -> dict[str, list[tuple[float, str]]]:
    """Symbol → sorted (epoch, hi|med|lo|none) BUY confidence (display only)."""
    out: dict[str, list[tuple[float, str]]] = {}
    if not trades:
        return out
    for raw in trades:
        if not isinstance(raw, Mapping):
            continue
        if str(raw.get("type") or "").upper() != "BUY":
            continue
        sym = str(raw.get("symbol") or "").strip().upper()
        if not sym:
            continue
        epoch = _parse_trade_epoch(str(raw.get("timestamp") or ""))
        if epoch is None:
            continue
        key = _normalize_buy_confidence(raw.get("confidence"))
        out.setdefault(sym, []).append((float(epoch), key))
    for sym, events in out.items():
        events.sort(key=lambda item: item[0])
    return out


def _entry_buy_confidence_bucket(
    h: dict[str, Any],
    buy_events: dict[str, list[tuple[float, str]]],
) -> str | None:
    """hi / med / lo / none from matching BUY; None if no entry or BUY row."""
    sym = str(h.get("symbol") or "").strip().upper()
    if not sym:
        return None
    raw = str(h.get("bought_at") or "").strip()
    if not raw:
        return None
    buy_epoch = _parse_trade_epoch(raw)
    if buy_epoch is None:
        return None
    for epoch, key in buy_events.get(sym) or []:
        if abs(epoch - buy_epoch) < 0.5:
            return key
    return None


def entry_buy_confidence_mark_returns(
    holdings: list[dict[str, Any]],
    trades: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Cost-weighted since-buy mark % by BUY-ledger AI confidence (display only).

    FinRobot + portfolio AI Group Matrix: lots whose matching BUY
    ``confidence`` was HIGH / MEDIUM / LOW vs blank (none = scanner-only /
    AI off). Contrasts with live Conf (newest debate memory). Missing
    ``bought_at`` / no matching BUY → unknown. Cluster n on labels.
    Strip only; not a research score; not a new gate — breakout LOW block
    stays in ``entry_guards``.
    """
    buys = _buy_confidence_events_by_symbol(trades)
    bands: dict[str, dict[str, Any]] = {
        "hi": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "med": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "lo": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "none": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
    }
    unknown_lots = 0
    for h in holdings:
        if not isinstance(h, dict):
            continue
        basis = _holding_cost_basis(h)
        if basis <= 0:
            continue
        key = _entry_buy_confidence_bucket(h, buys)
        if key is None:
            unknown_lots += 1
            continue
        bucket = bands[key]
        bucket["lots"] += 1
        pct = _holding_marked_pct(h)
        if pct is None:
            continue
        bucket["marked"] += 1
        bucket["cost"] += basis
        bucket["w_pct"] += basis * pct

    out: dict[str, Any] = {
        "entry_buy_conf_hi_pct": None,
        "entry_buy_conf_med_pct": None,
        "entry_buy_conf_lo_pct": None,
        "entry_buy_conf_none_pct": None,
        "entry_buy_conf_hi_label": "",
        "entry_buy_conf_med_label": "",
        "entry_buy_conf_lo_label": "",
        "entry_buy_conf_none_label": "",
        "entry_buy_conf_hi_lots": 0,
        "entry_buy_conf_med_lots": 0,
        "entry_buy_conf_lo_lots": 0,
        "entry_buy_conf_none_lots": 0,
        "entry_buy_conf_unknown_lots": unknown_lots,
        "entry_buy_conf_marks_ready": False,
        "entry_buy_conf_marks_bit": "",
    }
    bits: list[str] = []
    for key, short, field in (
        ("hi", "hi", "entry_buy_conf_hi"),
        ("med", "med", "entry_buy_conf_med"),
        ("lo", "lo", "entry_buy_conf_lo"),
        ("none", "none", "entry_buy_conf_none"),
    ):
        bucket = bands[key]
        has_lots = int(bucket["lots"]) > 0
        any_marked = int(bucket["marked"]) > 0
        pct: float | None = None
        if any_marked and float(bucket["cost"]) > 0:
            pct = float(bucket["w_pct"]) / float(bucket["cost"])
        cluster_n = int(bucket["marked"] if any_marked else bucket["lots"])
        label = _format_mark_pct(
            pct, has_lots=has_lots, any_marked=any_marked, cluster_n=cluster_n
        )
        out[f"{field}_lots"] = int(bucket["lots"])
        out[f"{field}_pct"] = round(pct, 2) if pct is not None else None
        out[f"{field}_label"] = label
        if label:
            bits.append(f"{short} {label}")
    if bits:
        out["entry_buy_conf_marks_ready"] = True
        out["entry_buy_conf_marks_bit"] = "buy-c " + " · ".join(bits)
    return out


def _normalize_buy_source(raw: Any) -> str:
    """Map ledger buy source to scan / rebal / other / none (display only)."""
    src = str(raw or "").strip().lower()
    if not src:
        return "none"
    if src == "scan":
        return "scan"
    if src in {"rebalance", "rebal"}:
        return "rebal"
    return "other"


def _buy_source_events_by_symbol(
    trades: Iterable[Mapping[str, Any]] | None,
) -> dict[str, list[tuple[float, str]]]:
    """Symbol → sorted (epoch, scan|rebal|other|none) BUY source (display only)."""
    out: dict[str, list[tuple[float, str]]] = {}
    if not trades:
        return out
    for raw in trades:
        if not isinstance(raw, Mapping):
            continue
        if str(raw.get("type") or "").upper() != "BUY":
            continue
        sym = str(raw.get("symbol") or "").strip().upper()
        if not sym:
            continue
        epoch = _parse_trade_epoch(str(raw.get("timestamp") or ""))
        if epoch is None:
            continue
        key = _normalize_buy_source(raw.get("source"))
        out.setdefault(sym, []).append((float(epoch), key))
    for sym, events in out.items():
        events.sort(key=lambda item: item[0])
    return out


def _entry_buy_source_bucket(
    h: dict[str, Any],
    buy_events: dict[str, list[tuple[float, str]]],
) -> str | None:
    """scan / rebal / other / none from matching BUY; None if no entry or BUY."""
    sym = str(h.get("symbol") or "").strip().upper()
    if not sym:
        return None
    raw = str(h.get("bought_at") or "").strip()
    if not raw:
        return None
    buy_epoch = _parse_trade_epoch(raw)
    if buy_epoch is None:
        return None
    for epoch, key in buy_events.get(sym) or []:
        if abs(epoch - buy_epoch) < 0.5:
            return key
    return None


def entry_buy_source_mark_returns(
    holdings: list[dict[str, Any]],
    trades: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Cost-weighted since-buy mark % by BUY-ledger fill source (display only).

    xang1234 + portfolio AI Group Matrix: lots whose matching BUY ``source``
    was scan / rebalance / other (interactive…) vs blank (none). Contrasts
    with live Scan on/off + List role. A6 earnings blackout applies to
    rebalance buys too — this cluster shows how lots entered. Missing
    ``bought_at`` / no matching BUY → unknown. Cluster n on labels.
    Strip only; not a new gate.
    """
    buys = _buy_source_events_by_symbol(trades)
    bands: dict[str, dict[str, Any]] = {
        "scan": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "rebal": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "other": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "none": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
    }
    unknown_lots = 0
    for h in holdings:
        if not isinstance(h, dict):
            continue
        basis = _holding_cost_basis(h)
        if basis <= 0:
            continue
        key = _entry_buy_source_bucket(h, buys)
        if key is None:
            unknown_lots += 1
            continue
        bucket = bands[key]
        bucket["lots"] += 1
        pct = _holding_marked_pct(h)
        if pct is None:
            continue
        bucket["marked"] += 1
        bucket["cost"] += basis
        bucket["w_pct"] += basis * pct

    out: dict[str, Any] = {
        "entry_buy_src_scan_pct": None,
        "entry_buy_src_rebal_pct": None,
        "entry_buy_src_other_pct": None,
        "entry_buy_src_none_pct": None,
        "entry_buy_src_scan_label": "",
        "entry_buy_src_rebal_label": "",
        "entry_buy_src_other_label": "",
        "entry_buy_src_none_label": "",
        "entry_buy_src_scan_lots": 0,
        "entry_buy_src_rebal_lots": 0,
        "entry_buy_src_other_lots": 0,
        "entry_buy_src_none_lots": 0,
        "entry_buy_src_unknown_lots": unknown_lots,
        "entry_buy_src_marks_ready": False,
        "entry_buy_src_marks_bit": "",
    }
    bits: list[str] = []
    for key, short, field in (
        ("scan", "scan", "entry_buy_src_scan"),
        ("rebal", "rebal", "entry_buy_src_rebal"),
        ("other", "other", "entry_buy_src_other"),
        ("none", "none", "entry_buy_src_none"),
    ):
        bucket = bands[key]
        has_lots = int(bucket["lots"]) > 0
        any_marked = int(bucket["marked"]) > 0
        pct: float | None = None
        if any_marked and float(bucket["cost"]) > 0:
            pct = float(bucket["w_pct"]) / float(bucket["cost"])
        cluster_n = int(bucket["marked"] if any_marked else bucket["lots"])
        label = _format_mark_pct(
            pct, has_lots=has_lots, any_marked=any_marked, cluster_n=cluster_n
        )
        out[f"{field}_lots"] = int(bucket["lots"])
        out[f"{field}_pct"] = round(pct, 2) if pct is not None else None
        out[f"{field}_label"] = label
        if label:
            bits.append(f"{short} {label}")
    if bits:
        out["entry_buy_src_marks_ready"] = True
        out["entry_buy_src_marks_bit"] = "src " + " · ".join(bits)
    return out


def _normalize_buy_score(raw: Any) -> str:
    """Map ledger buy score to hi / mid / lo / none (display only)."""
    if raw is None or raw == "":
        return "none"
    try:
        sc = float(raw)
    except (TypeError, ValueError):
        return "none"
    if sc >= float(SCAN_SCORE_HI):
        return "hi"
    if sc >= float(SCAN_SCORE_MID):
        return "mid"
    return "lo"


def _buy_score_events_by_symbol(
    trades: Iterable[Mapping[str, Any]] | None,
) -> dict[str, list[tuple[float, str]]]:
    """Symbol → sorted (epoch, hi|mid|lo|none) BUY score band (display only)."""
    out: dict[str, list[tuple[float, str]]] = {}
    if not trades:
        return out
    for raw in trades:
        if not isinstance(raw, Mapping):
            continue
        if str(raw.get("type") or "").upper() != "BUY":
            continue
        sym = str(raw.get("symbol") or "").strip().upper()
        if not sym:
            continue
        epoch = _parse_trade_epoch(str(raw.get("timestamp") or ""))
        if epoch is None:
            continue
        key = _normalize_buy_score(raw.get("score"))
        out.setdefault(sym, []).append((float(epoch), key))
    for sym, events in out.items():
        events.sort(key=lambda item: item[0])
    return out


def _entry_buy_score_bucket(
    h: dict[str, Any],
    buy_events: dict[str, list[tuple[float, str]]],
) -> str | None:
    """hi / mid / lo / none from matching BUY; None if no entry or BUY row."""
    sym = str(h.get("symbol") or "").strip().upper()
    if not sym:
        return None
    raw = str(h.get("bought_at") or "").strip()
    if not raw:
        return None
    buy_epoch = _parse_trade_epoch(raw)
    if buy_epoch is None:
        return None
    for epoch, key in buy_events.get(sym) or []:
        if abs(epoch - buy_epoch) < 0.5:
            return key
    return None


def entry_buy_score_mark_returns(
    holdings: list[dict[str, Any]],
    trades: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Cost-weighted since-buy mark % by BUY-ledger screener score (display only).

    xang1234 + portfolio AI Group Matrix: lots whose matching BUY ``score``
    was hi (≥50) / mid (≥25) / lo / none (blank). Same bands as live Score.
    Contrasts entry-time rank with current scan Score. Missing ``bought_at``
    / no matching BUY → unknown. Cluster n on labels. Strip only; not a
    research score; not a new gate.
    """
    buys = _buy_score_events_by_symbol(trades)
    bands: dict[str, dict[str, Any]] = {
        "hi": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "mid": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "lo": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "none": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
    }
    unknown_lots = 0
    for h in holdings:
        if not isinstance(h, dict):
            continue
        basis = _holding_cost_basis(h)
        if basis <= 0:
            continue
        key = _entry_buy_score_bucket(h, buys)
        if key is None:
            unknown_lots += 1
            continue
        bucket = bands[key]
        bucket["lots"] += 1
        pct = _holding_marked_pct(h)
        if pct is None:
            continue
        bucket["marked"] += 1
        bucket["cost"] += basis
        bucket["w_pct"] += basis * pct

    out: dict[str, Any] = {
        "entry_buy_score_hi_pct": None,
        "entry_buy_score_mid_pct": None,
        "entry_buy_score_lo_pct": None,
        "entry_buy_score_none_pct": None,
        "entry_buy_score_hi_label": "",
        "entry_buy_score_mid_label": "",
        "entry_buy_score_lo_label": "",
        "entry_buy_score_none_label": "",
        "entry_buy_score_hi_lots": 0,
        "entry_buy_score_mid_lots": 0,
        "entry_buy_score_lo_lots": 0,
        "entry_buy_score_none_lots": 0,
        "entry_buy_score_unknown_lots": unknown_lots,
        "entry_buy_score_marks_ready": False,
        "entry_buy_score_marks_bit": "",
        "entry_buy_score_hi_floor": float(SCAN_SCORE_HI),
        "entry_buy_score_mid_floor": float(SCAN_SCORE_MID),
    }
    bits: list[str] = []
    for key, short, field in (
        ("hi", "hi", "entry_buy_score_hi"),
        ("mid", "mid", "entry_buy_score_mid"),
        ("lo", "lo", "entry_buy_score_lo"),
        ("none", "none", "entry_buy_score_none"),
    ):
        bucket = bands[key]
        has_lots = int(bucket["lots"]) > 0
        any_marked = int(bucket["marked"]) > 0
        pct: float | None = None
        if any_marked and float(bucket["cost"]) > 0:
            pct = float(bucket["w_pct"]) / float(bucket["cost"])
        cluster_n = int(bucket["marked"] if any_marked else bucket["lots"])
        label = _format_mark_pct(
            pct, has_lots=has_lots, any_marked=any_marked, cluster_n=cluster_n
        )
        out[f"{field}_lots"] = int(bucket["lots"])
        out[f"{field}_pct"] = round(pct, 2) if pct is not None else None
        out[f"{field}_label"] = label
        if label:
            bits.append(f"{short} {label}")
    if bits:
        out["entry_buy_score_marks_ready"] = True
        out["entry_buy_score_marks_bit"] = "buy-s " + " · ".join(bits)
    return out


def _normalize_buy_strategy(raw: Any) -> str:
    """Map ledger buy strategy to brk / mom / oth / none (display only)."""
    strat = str(raw or "").strip().lower()
    if not strat:
        return "none"
    if strat == "breakout":
        return "brk"
    if strat == "momentum":
        return "mom"
    return "oth"


def _buy_strategy_events_by_symbol(
    trades: Iterable[Mapping[str, Any]] | None,
) -> dict[str, list[tuple[float, str]]]:
    """Symbol → sorted (epoch, brk|mom|oth|none) BUY strategy (display only)."""
    out: dict[str, list[tuple[float, str]]] = {}
    if not trades:
        return out
    for raw in trades:
        if not isinstance(raw, Mapping):
            continue
        if str(raw.get("type") or "").upper() != "BUY":
            continue
        sym = str(raw.get("symbol") or "").strip().upper()
        if not sym:
            continue
        epoch = _parse_trade_epoch(str(raw.get("timestamp") or ""))
        if epoch is None:
            continue
        key = _normalize_buy_strategy(raw.get("strategy"))
        out.setdefault(sym, []).append((float(epoch), key))
    for sym, events in out.items():
        events.sort(key=lambda item: item[0])
    return out


def _entry_buy_strategy_bucket(
    h: dict[str, Any],
    buy_events: dict[str, list[tuple[float, str]]],
) -> str | None:
    """brk / mom / oth / none from matching BUY; None if no entry or BUY row."""
    sym = str(h.get("symbol") or "").strip().upper()
    if not sym:
        return None
    raw = str(h.get("bought_at") or "").strip()
    if not raw:
        return None
    buy_epoch = _parse_trade_epoch(raw)
    if buy_epoch is None:
        return None
    for epoch, key in buy_events.get(sym) or []:
        if abs(epoch - buy_epoch) < 0.5:
            return key
    return None


def entry_buy_strategy_mark_returns(
    holdings: list[dict[str, Any]],
    trades: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Cost-weighted since-buy mark % by BUY-ledger strategy (display only).

    xang1234 screener + FinRobot + portfolio AI Group Matrix: lots whose
    matching BUY ``strategy`` was breakout (brk) / momentum (mom) / other
    (oth) vs blank (none). Contrasts entry thesis with live List role +
    breakout-guard glance. Missing ``bought_at`` / no matching BUY →
    unknown. Cluster n on labels. Strip only; not a research score; not a
    new gate — breakout AI BUY + pullback stay in ``entry_guards``.
    """
    buys = _buy_strategy_events_by_symbol(trades)
    bands: dict[str, dict[str, Any]] = {
        "brk": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "mom": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "oth": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "none": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
    }
    unknown_lots = 0
    for h in holdings:
        if not isinstance(h, dict):
            continue
        basis = _holding_cost_basis(h)
        if basis <= 0:
            continue
        key = _entry_buy_strategy_bucket(h, buys)
        if key is None:
            unknown_lots += 1
            continue
        bucket = bands[key]
        bucket["lots"] += 1
        pct = _holding_marked_pct(h)
        if pct is None:
            continue
        bucket["marked"] += 1
        bucket["cost"] += basis
        bucket["w_pct"] += basis * pct

    out: dict[str, Any] = {
        "entry_buy_strat_brk_pct": None,
        "entry_buy_strat_mom_pct": None,
        "entry_buy_strat_oth_pct": None,
        "entry_buy_strat_none_pct": None,
        "entry_buy_strat_brk_label": "",
        "entry_buy_strat_mom_label": "",
        "entry_buy_strat_oth_label": "",
        "entry_buy_strat_none_label": "",
        "entry_buy_strat_brk_lots": 0,
        "entry_buy_strat_mom_lots": 0,
        "entry_buy_strat_oth_lots": 0,
        "entry_buy_strat_none_lots": 0,
        "entry_buy_strat_unknown_lots": unknown_lots,
        "entry_buy_strat_marks_ready": False,
        "entry_buy_strat_marks_bit": "",
    }
    bits: list[str] = []
    for key, short, field in (
        ("brk", "brk", "entry_buy_strat_brk"),
        ("mom", "mom", "entry_buy_strat_mom"),
        ("oth", "oth", "entry_buy_strat_oth"),
        ("none", "none", "entry_buy_strat_none"),
    ):
        bucket = bands[key]
        has_lots = int(bucket["lots"]) > 0
        any_marked = int(bucket["marked"]) > 0
        pct: float | None = None
        if any_marked and float(bucket["cost"]) > 0:
            pct = float(bucket["w_pct"]) / float(bucket["cost"])
        cluster_n = int(bucket["marked"] if any_marked else bucket["lots"])
        label = _format_mark_pct(
            pct, has_lots=has_lots, any_marked=any_marked, cluster_n=cluster_n
        )
        out[f"{field}_lots"] = int(bucket["lots"])
        out[f"{field}_pct"] = round(pct, 2) if pct is not None else None
        out[f"{field}_label"] = label
        if label:
            bits.append(f"{short} {label}")
    if bits:
        out["entry_buy_strat_marks_ready"] = True
        out["entry_buy_strat_marks_bit"] = "strat " + " · ".join(bits)
    return out


def _buy_cash_frac_from_row(raw: Mapping[str, Any]) -> float | None:
    """BUY total_cost / (cash_remaining + total_cost); None if unreadable."""
    try:
        total_raw = raw.get("total_cost")
        if total_raw is None:
            cost = float(raw.get("cost") or 0.0)
            commission = float(raw.get("commission") or 0.0)
            total = cost + commission if cost > 0 else 0.0
        else:
            total = float(total_raw)
        cash_rem = float(raw.get("cash_remaining"))
    except (TypeError, ValueError):
        return None
    if total <= 0 or cash_rem < 0:
        return None
    pre_cash = cash_rem + total
    if pre_cash <= 0:
        return None
    return total / pre_cash


def _normalize_buy_size_frac(frac: float | None) -> str:
    """Map entry cash fraction to fat / ok / thin / none (display only)."""
    if frac is None:
        return "none"
    if frac >= ENTRY_SIZE_FAT_FRAC:
        return "fat"
    if frac < ENTRY_SIZE_THIN_FRAC:
        return "thin"
    return "ok"


def _buy_size_events_by_symbol(
    trades: Iterable[Mapping[str, Any]] | None,
) -> dict[str, list[tuple[float, str]]]:
    """Symbol → sorted (epoch, fat|ok|thin|none) BUY cash-frac band."""
    out: dict[str, list[tuple[float, str]]] = {}
    if not trades:
        return out
    for raw in trades:
        if not isinstance(raw, Mapping):
            continue
        if str(raw.get("type") or "").upper() != "BUY":
            continue
        sym = str(raw.get("symbol") or "").strip().upper()
        if not sym:
            continue
        epoch = _parse_trade_epoch(str(raw.get("timestamp") or ""))
        if epoch is None:
            continue
        key = _normalize_buy_size_frac(_buy_cash_frac_from_row(raw))
        out.setdefault(sym, []).append((float(epoch), key))
    for sym, events in out.items():
        events.sort(key=lambda item: item[0])
    return out


def _entry_buy_size_bucket(
    h: dict[str, Any],
    buy_events: dict[str, list[tuple[float, str]]],
) -> str | None:
    """fat / ok / thin / none from matching BUY; None if no entry or BUY row."""
    sym = str(h.get("symbol") or "").strip().upper()
    if not sym:
        return None
    raw = str(h.get("bought_at") or "").strip()
    if not raw:
        return None
    buy_epoch = _parse_trade_epoch(raw)
    if buy_epoch is None:
        return None
    for epoch, key in buy_events.get(sym) or []:
        if abs(epoch - buy_epoch) < 0.5:
            return key
    return None


def entry_buy_size_mark_returns(
    holdings: list[dict[str, Any]],
    trades: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Cost-weighted since-buy mark % by BUY cash-fraction vs sizer (display).

    tradermonty position-sizer + portfolio AI Group Matrix: lots whose matching
    BUY used fat (≥15% of pre-buy cash) / ok (5–15%, ~10% default) / thin
    (<5%) / none (ledger missing total_cost·cash_remaining). Contrasts entry
    size with Overview next-buy sizer. Missing ``bought_at`` / no matching BUY
    → unknown. Cluster n on labels. Strip only; not a new gate — live size
    stays ``suggest_entry_notional`` / trader cash frac.
    """
    buys = _buy_size_events_by_symbol(trades)
    bands: dict[str, dict[str, Any]] = {
        "fat": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "ok": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "thin": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "none": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
    }
    unknown_lots = 0
    for h in holdings:
        if not isinstance(h, dict):
            continue
        basis = _holding_cost_basis(h)
        if basis <= 0:
            continue
        key = _entry_buy_size_bucket(h, buys)
        if key is None:
            unknown_lots += 1
            continue
        bucket = bands[key]
        bucket["lots"] += 1
        pct = _holding_marked_pct(h)
        if pct is None:
            continue
        bucket["marked"] += 1
        bucket["cost"] += basis
        bucket["w_pct"] += basis * pct

    out: dict[str, Any] = {
        "entry_buy_size_fat_pct": None,
        "entry_buy_size_ok_pct": None,
        "entry_buy_size_thin_pct": None,
        "entry_buy_size_none_pct": None,
        "entry_buy_size_fat_label": "",
        "entry_buy_size_ok_label": "",
        "entry_buy_size_thin_label": "",
        "entry_buy_size_none_label": "",
        "entry_buy_size_fat_lots": 0,
        "entry_buy_size_ok_lots": 0,
        "entry_buy_size_thin_lots": 0,
        "entry_buy_size_none_lots": 0,
        "entry_buy_size_unknown_lots": unknown_lots,
        "entry_buy_size_marks_ready": False,
        "entry_buy_size_marks_bit": "",
        "entry_buy_size_default_frac": float(DEFAULT_ENTRY_CASH_FRAC),
        "entry_buy_size_fat_floor": float(ENTRY_SIZE_FAT_FRAC),
        "entry_buy_size_thin_floor": float(ENTRY_SIZE_THIN_FRAC),
    }
    bits: list[str] = []
    for key, short, field in (
        ("fat", "fat", "entry_buy_size_fat"),
        ("ok", "ok", "entry_buy_size_ok"),
        ("thin", "thin", "entry_buy_size_thin"),
        ("none", "none", "entry_buy_size_none"),
    ):
        bucket = bands[key]
        has_lots = int(bucket["lots"]) > 0
        any_marked = int(bucket["marked"]) > 0
        pct: float | None = None
        if any_marked and float(bucket["cost"]) > 0:
            pct = float(bucket["w_pct"]) / float(bucket["cost"])
        cluster_n = int(bucket["marked"] if any_marked else bucket["lots"])
        label = _format_mark_pct(
            pct, has_lots=has_lots, any_marked=any_marked, cluster_n=cluster_n
        )
        out[f"{field}_lots"] = int(bucket["lots"])
        out[f"{field}_pct"] = round(pct, 2) if pct is not None else None
        out[f"{field}_label"] = label
        if label:
            bits.append(f"{short} {label}")
    if bits:
        out["entry_buy_size_marks_ready"] = True
        out["entry_buy_size_marks_bit"] = "buy-% " + " · ".join(bits)
    return out


def _entry_concentration_bucket(
    h: dict[str, Any],
    *,
    equity: float,
    max_name_pct: float,
) -> str | None:
    """at / under soft single-name cap from market weight; None if unreadable."""
    if equity <= 0 or max_name_pct <= 0:
        return None
    try:
        mv = float(h.get("market_value") or 0.0)
    except (TypeError, ValueError):
        return None
    if mv <= 0:
        # Fall back to cost when mark is missing (cost-flat desk rows).
        mv = _holding_cost_basis(h)
    if mv <= 0:
        return None
    weight_pct = (mv / equity) * 100.0
    if weight_pct >= max_name_pct:
        return "at"
    return "under"


def entry_concentration_mark_returns(
    holdings: list[dict[str, Any]],
    *,
    equity: float,
    max_name_pct: float = DEFAULT_MAX_NAME_PCT,
) -> dict[str, Any]:
    """Cost-weighted since-buy mark % by soft concentration cap (display only).

    tradermonty multi-asset replay ``max_position_pct`` breach honesty +
    portfolio AI Group Matrix: lots whose market weight is ≥ soft single-name
    cap (default 30% equity) → ``at`` vs ``under``. Unreadable equity/weight
    → skipped. Cluster n on labels. Strip only; not a new gate — live soft
    halt stays ``concentration_allows``.
    """
    try:
        equity_f = float(equity)
        cap = abs(float(max_name_pct))
    except (TypeError, ValueError):
        equity_f = 0.0
        cap = 0.0
    bands: dict[str, dict[str, Any]] = {
        "at": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "under": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
    }
    unknown_lots = 0
    for h in holdings:
        if not isinstance(h, dict):
            continue
        basis = _holding_cost_basis(h)
        if basis <= 0:
            continue
        key = _entry_concentration_bucket(h, equity=equity_f, max_name_pct=cap)
        if key is None:
            unknown_lots += 1
            continue
        bucket = bands[key]
        bucket["lots"] += 1
        pct = _holding_marked_pct(h)
        if pct is None:
            continue
        bucket["marked"] += 1
        bucket["cost"] += basis
        bucket["w_pct"] += basis * pct

    out: dict[str, Any] = {
        "entry_conc_at_pct": None,
        "entry_conc_under_pct": None,
        "entry_conc_at_label": "",
        "entry_conc_under_label": "",
        "entry_conc_at_lots": 0,
        "entry_conc_under_lots": 0,
        "entry_conc_unknown_lots": unknown_lots,
        "entry_conc_cap_pct": round(cap, 1) if cap > 0 else float(DEFAULT_MAX_NAME_PCT),
        "entry_conc_marks_ready": False,
        "entry_conc_marks_bit": "",
    }
    bits: list[str] = []
    for key, short, field in (
        ("at", "at", "entry_conc_at"),
        ("under", "under", "entry_conc_under"),
    ):
        bucket = bands[key]
        has_lots = int(bucket["lots"]) > 0
        any_marked = int(bucket["marked"]) > 0
        pct: float | None = None
        if any_marked and float(bucket["cost"]) > 0:
            pct = float(bucket["w_pct"]) / float(bucket["cost"])
        cluster_n = int(bucket["marked"] if any_marked else bucket["lots"])
        label = _format_mark_pct(
            pct, has_lots=has_lots, any_marked=any_marked, cluster_n=cluster_n
        )
        out[f"{field}_lots"] = int(bucket["lots"])
        out[f"{field}_pct"] = round(pct, 2) if pct is not None else None
        out[f"{field}_label"] = label
        if label:
            bits.append(f"{short} {label}")
    if bits:
        out["entry_conc_marks_ready"] = True
        out["entry_conc_marks_bit"] = "cap " + " · ".join(bits)
    return out


def scan_mark_returns(
    holdings: list[dict[str, Any]],
    scan_symbols: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Cost-weighted since-buy mark % by scan-list membership (display only).

    xang1234 screener + tradermonty stale-rotation cluster: lots still on
    the full opportunity list vs off-list. Empty/missing scan set → no
    marks (not a silent all-off). Cluster n on labels. Strip only; not a
    gate; not calendar 1w/1m.
    """
    scan: set[str] = set()
    for sym in scan_symbols or []:
        s = str(sym or "").strip()
        if s:
            scan.add(s)
    bands: dict[str, dict[str, Any]] = {
        "on": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "off": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
    }
    out: dict[str, Any] = {
        "scan_on_pct": None,
        "scan_off_pct": None,
        "scan_on_label": "",
        "scan_off_label": "",
        "scan_on_lots": 0,
        "scan_off_lots": 0,
        "scan_marks_ready": False,
        "scan_marks_bit": "",
    }
    if not scan:
        return out

    for h in holdings:
        if not isinstance(h, dict):
            continue
        basis = _holding_cost_basis(h)
        if basis <= 0:
            continue
        sym = str(h.get("symbol") or "").strip()
        if not sym:
            continue
        key = "on" if sym in scan else "off"
        bucket = bands[key]
        bucket["lots"] += 1
        pct = _holding_marked_pct(h)
        if pct is None:
            continue
        bucket["marked"] += 1
        bucket["cost"] += basis
        bucket["w_pct"] += basis * pct

    bits: list[str] = []
    for key, short, field in (
        ("on", "on", "scan_on"),
        ("off", "off", "scan_off"),
    ):
        bucket = bands[key]
        has_lots = int(bucket["lots"]) > 0
        any_marked = int(bucket["marked"]) > 0
        pct: float | None = None
        if any_marked and float(bucket["cost"]) > 0:
            pct = float(bucket["w_pct"]) / float(bucket["cost"])
        cluster_n = int(bucket["marked"] if any_marked else bucket["lots"])
        label = _format_mark_pct(
            pct, has_lots=has_lots, any_marked=any_marked, cluster_n=cluster_n
        )
        out[f"{field}_lots"] = int(bucket["lots"])
        out[f"{field}_pct"] = round(pct, 2) if pct is not None else None
        out[f"{field}_label"] = label
        if label:
            bits.append(f"{short} {label}")
    if bits:
        out["scan_marks_ready"] = True
        out["scan_marks_bit"] = "scan " + " · ".join(bits)
    return out


def scan_list_mark_returns(
    holdings: list[dict[str, Any]],
    *,
    leaders: Iterable[str] | None = None,
    breakouts: Iterable[str] | None = None,
    recommendations: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Cost-weighted since-buy mark % by screener list role (display only).

    xang1234 screener + Group Matrix: crypto leaders vs stock breakouts vs
    plain recommendations vs off-list. Priority lead > brk > rec > off.
    Empty lists → no marks (not a silent all-off). Cluster n on labels.
    Strip only; not a gate; not calendar 1w/1m.
    """

    def _norm(syms: Iterable[str] | None) -> set[str]:
        out: set[str] = set()
        for raw in syms or []:
            s = str(raw or "").strip().upper()
            if s:
                out.add(s)
        return out

    lead = _norm(leaders)
    brk = _norm(breakouts)
    rec = _norm(recommendations)
    bands: dict[str, dict[str, Any]] = {
        "lead": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "brk": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "rec": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "off": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
    }
    out: dict[str, Any] = {
        "scan_list_lead_pct": None,
        "scan_list_brk_pct": None,
        "scan_list_rec_pct": None,
        "scan_list_off_pct": None,
        "scan_list_lead_label": "",
        "scan_list_brk_label": "",
        "scan_list_rec_label": "",
        "scan_list_off_label": "",
        "scan_list_lead_lots": 0,
        "scan_list_brk_lots": 0,
        "scan_list_rec_lots": 0,
        "scan_list_off_lots": 0,
        "scan_list_marks_ready": False,
        "scan_list_marks_bit": "",
    }
    if not lead and not brk and not rec:
        return out

    for h in holdings:
        if not isinstance(h, dict):
            continue
        basis = _holding_cost_basis(h)
        if basis <= 0:
            continue
        sym = str(h.get("symbol") or "").strip().upper()
        if not sym:
            continue
        if sym in lead:
            key = "lead"
        elif sym in brk:
            key = "brk"
        elif sym in rec:
            key = "rec"
        else:
            key = "off"
        bucket = bands[key]
        bucket["lots"] += 1
        pct = _holding_marked_pct(h)
        if pct is None:
            continue
        bucket["marked"] += 1
        bucket["cost"] += basis
        bucket["w_pct"] += basis * pct

    bits: list[str] = []
    for key, short, field in (
        ("lead", "lead", "scan_list_lead"),
        ("brk", "brk", "scan_list_brk"),
        ("rec", "rec", "scan_list_rec"),
        ("off", "off", "scan_list_off"),
    ):
        bucket = bands[key]
        has_lots = int(bucket["lots"]) > 0
        any_marked = int(bucket["marked"]) > 0
        pct: float | None = None
        if any_marked and float(bucket["cost"]) > 0:
            pct = float(bucket["w_pct"]) / float(bucket["cost"])
        cluster_n = int(bucket["marked"] if any_marked else bucket["lots"])
        label = _format_mark_pct(
            pct, has_lots=has_lots, any_marked=any_marked, cluster_n=cluster_n
        )
        out[f"{field}_lots"] = int(bucket["lots"])
        out[f"{field}_pct"] = round(pct, 2) if pct is not None else None
        out[f"{field}_label"] = label
        if label:
            bits.append(f"{short} {label}")
    if bits:
        out["scan_list_marks_ready"] = True
        out["scan_list_marks_bit"] = "list " + " · ".join(bits)
    return out


def scan_score_mark_returns(
    holdings: list[dict[str, Any]],
    score_by_symbol: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Cost-weighted since-buy mark % by current screener score (display only).

    xang1234 + portfolio AI Group Matrix: hi (≥50) / mid (≥25) / lo (scored
    but <25) / off (not on score map). Thresholds match recommender BUY
    confidence bands. ``score_by_symbol`` None → skip. Empty map → all off.
    Cluster n on labels. Strip only; not a gate; not a research score.
    """
    bands: dict[str, dict[str, Any]] = {
        "hi": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "mid": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "lo": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "off": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
    }
    out: dict[str, Any] = {
        "scan_score_hi_pct": None,
        "scan_score_mid_pct": None,
        "scan_score_lo_pct": None,
        "scan_score_off_pct": None,
        "scan_score_hi_label": "",
        "scan_score_mid_label": "",
        "scan_score_lo_label": "",
        "scan_score_off_label": "",
        "scan_score_hi_lots": 0,
        "scan_score_mid_lots": 0,
        "scan_score_lo_lots": 0,
        "scan_score_off_lots": 0,
        "scan_score_marks_ready": False,
        "scan_score_marks_bit": "",
        "scan_score_hi_floor": float(SCAN_SCORE_HI),
        "scan_score_mid_floor": float(SCAN_SCORE_MID),
    }
    if score_by_symbol is None:
        return out

    scores: dict[str, float] = {}
    for raw_sym, raw_score in score_by_symbol.items():
        sym = str(raw_sym or "").strip().upper()
        if not sym:
            continue
        try:
            scores[sym] = float(raw_score)
        except (TypeError, ValueError):
            continue

    for h in holdings:
        if not isinstance(h, dict):
            continue
        basis = _holding_cost_basis(h)
        if basis <= 0:
            continue
        sym = str(h.get("symbol") or "").strip().upper()
        if not sym:
            continue
        if sym not in scores:
            key = "off"
        else:
            sc = scores[sym]
            if sc >= SCAN_SCORE_HI:
                key = "hi"
            elif sc >= SCAN_SCORE_MID:
                key = "mid"
            else:
                key = "lo"
        bucket = bands[key]
        bucket["lots"] += 1
        pct = _holding_marked_pct(h)
        if pct is None:
            continue
        bucket["marked"] += 1
        bucket["cost"] += basis
        bucket["w_pct"] += basis * pct

    bits: list[str] = []
    for key, short, field in (
        ("hi", "hi", "scan_score_hi"),
        ("mid", "mid", "scan_score_mid"),
        ("lo", "lo", "scan_score_lo"),
        ("off", "off", "scan_score_off"),
    ):
        bucket = bands[key]
        has_lots = int(bucket["lots"]) > 0
        any_marked = int(bucket["marked"]) > 0
        pct: float | None = None
        if any_marked and float(bucket["cost"]) > 0:
            pct = float(bucket["w_pct"]) / float(bucket["cost"])
        cluster_n = int(bucket["marked"] if any_marked else bucket["lots"])
        label = _format_mark_pct(
            pct, has_lots=has_lots, any_marked=any_marked, cluster_n=cluster_n
        )
        out[f"{field}_lots"] = int(bucket["lots"])
        out[f"{field}_pct"] = round(pct, 2) if pct is not None else None
        out[f"{field}_label"] = label
        if label:
            bits.append(f"{short} {label}")
    if bits:
        out["scan_score_marks_ready"] = True
        out["scan_score_marks_bit"] = "score " + " · ".join(bits)
    return out


def scan_near_high_mark_returns(
    holdings: list[dict[str, Any]],
    pct_from_high_by_symbol: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Cost-weighted since-buy mark % by scan pct_from_high (display only).

    xang1234 StockBee + portfolio AI Group Matrix: near (≥ −5% from high,
    scanner breakout band) / mid (≥ −20%) / deep (< −20%) / off (not on
    map). ``pct_from_high_by_symbol`` None → skip. Empty map → all off.
    Cluster n on labels. Strip only; not a gate.
    """
    bands: dict[str, dict[str, Any]] = {
        "near": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "mid": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "deep": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "off": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
    }
    out: dict[str, Any] = {
        "scan_near_high_near_pct": None,
        "scan_near_high_mid_pct": None,
        "scan_near_high_deep_pct": None,
        "scan_near_high_off_pct": None,
        "scan_near_high_near_label": "",
        "scan_near_high_mid_label": "",
        "scan_near_high_deep_label": "",
        "scan_near_high_off_label": "",
        "scan_near_high_near_lots": 0,
        "scan_near_high_mid_lots": 0,
        "scan_near_high_deep_lots": 0,
        "scan_near_high_off_lots": 0,
        "scan_near_high_marks_ready": False,
        "scan_near_high_marks_bit": "",
        "scan_near_high_floor": float(SCAN_NEAR_HIGH_PCT),
        "scan_near_high_mid_floor": float(SCAN_NEAR_HIGH_MID),
    }
    if pct_from_high_by_symbol is None:
        return out

    highs: dict[str, float] = {}
    for raw_sym, raw_pct in pct_from_high_by_symbol.items():
        sym = str(raw_sym or "").strip().upper()
        if not sym:
            continue
        try:
            highs[sym] = float(raw_pct)
        except (TypeError, ValueError):
            continue

    for h in holdings:
        if not isinstance(h, dict):
            continue
        basis = _holding_cost_basis(h)
        if basis <= 0:
            continue
        sym = str(h.get("symbol") or "").strip().upper()
        if not sym:
            continue
        if sym not in highs:
            key = "off"
        else:
            pct_h = highs[sym]
            if pct_h >= SCAN_NEAR_HIGH_PCT:
                key = "near"
            elif pct_h >= SCAN_NEAR_HIGH_MID:
                key = "mid"
            else:
                key = "deep"
        bucket = bands[key]
        bucket["lots"] += 1
        pct = _holding_marked_pct(h)
        if pct is None:
            continue
        bucket["marked"] += 1
        bucket["cost"] += basis
        bucket["w_pct"] += basis * pct

    bits: list[str] = []
    for key, short, field in (
        ("near", "near", "scan_near_high_near"),
        ("mid", "mid", "scan_near_high_mid"),
        ("deep", "deep", "scan_near_high_deep"),
        ("off", "off", "scan_near_high_off"),
    ):
        bucket = bands[key]
        has_lots = int(bucket["lots"]) > 0
        any_marked = int(bucket["marked"]) > 0
        pct: float | None = None
        if any_marked and float(bucket["cost"]) > 0:
            pct = float(bucket["w_pct"]) / float(bucket["cost"])
        cluster_n = int(bucket["marked"] if any_marked else bucket["lots"])
        label = _format_mark_pct(
            pct, has_lots=has_lots, any_marked=any_marked, cluster_n=cluster_n
        )
        out[f"{field}_lots"] = int(bucket["lots"])
        out[f"{field}_pct"] = round(pct, 2) if pct is not None else None
        out[f"{field}_label"] = label
        if label:
            bits.append(f"{short} {label}")
    if bits:
        out["scan_near_high_marks_ready"] = True
        out["scan_near_high_marks_bit"] = "high " + " · ".join(bits)
    return out


def scan_mover_mark_returns(
    holdings: list[dict[str, Any]],
    change_by_symbol: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Cost-weighted since-buy mark % by scan day change (display only).

    xang1234 StockBee + portfolio AI Group Matrix: hot (≥ +4%) / cold
    (≤ −4%) / quiet (on map, |chg| < 4%) / off (not on map). Threshold
    matches Breadth ±4% movers. ``change_by_symbol`` None → skip. Empty
    map → all off. Cluster n on labels. Strip only; not a gate.
    """
    bands: dict[str, dict[str, Any]] = {
        "hot": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "cold": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "quiet": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "off": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
    }
    out: dict[str, Any] = {
        "scan_mover_hot_pct": None,
        "scan_mover_cold_pct": None,
        "scan_mover_quiet_pct": None,
        "scan_mover_off_pct": None,
        "scan_mover_hot_label": "",
        "scan_mover_cold_label": "",
        "scan_mover_quiet_label": "",
        "scan_mover_off_label": "",
        "scan_mover_hot_lots": 0,
        "scan_mover_cold_lots": 0,
        "scan_mover_quiet_lots": 0,
        "scan_mover_off_lots": 0,
        "scan_mover_marks_ready": False,
        "scan_mover_marks_bit": "",
        "scan_mover_floor": float(SCAN_MOVER_PCT),
    }
    if change_by_symbol is None:
        return out

    changes: dict[str, float] = {}
    for raw_sym, raw_chg in change_by_symbol.items():
        sym = str(raw_sym or "").strip().upper()
        if not sym:
            continue
        try:
            changes[sym] = float(raw_chg)
        except (TypeError, ValueError):
            continue

    floor = float(SCAN_MOVER_PCT)
    for h in holdings:
        if not isinstance(h, dict):
            continue
        basis = _holding_cost_basis(h)
        if basis <= 0:
            continue
        sym = str(h.get("symbol") or "").strip().upper()
        if not sym:
            continue
        if sym not in changes:
            key = "off"
        else:
            chg = changes[sym]
            if chg >= floor:
                key = "hot"
            elif chg <= -floor:
                key = "cold"
            else:
                key = "quiet"
        bucket = bands[key]
        bucket["lots"] += 1
        pct = _holding_marked_pct(h)
        if pct is None:
            continue
        bucket["marked"] += 1
        bucket["cost"] += basis
        bucket["w_pct"] += basis * pct

    bits: list[str] = []
    for key, short, field in (
        ("hot", "hot", "scan_mover_hot"),
        ("cold", "cold", "scan_mover_cold"),
        ("quiet", "quiet", "scan_mover_quiet"),
        ("off", "off", "scan_mover_off"),
    ):
        bucket = bands[key]
        has_lots = int(bucket["lots"]) > 0
        any_marked = int(bucket["marked"]) > 0
        pct: float | None = None
        if any_marked and float(bucket["cost"]) > 0:
            pct = float(bucket["w_pct"]) / float(bucket["cost"])
        cluster_n = int(bucket["marked"] if any_marked else bucket["lots"])
        label = _format_mark_pct(
            pct, has_lots=has_lots, any_marked=any_marked, cluster_n=cluster_n
        )
        out[f"{field}_lots"] = int(bucket["lots"])
        out[f"{field}_pct"] = round(pct, 2) if pct is not None else None
        out[f"{field}_label"] = label
        if label:
            bits.append(f"{short} {label}")
    if bits:
        out["scan_mover_marks_ready"] = True
        out["scan_mover_marks_bit"] = "move " + " · ".join(bits)
    return out


def ai_debate_mark_returns(
    holdings: list[dict[str, Any]],
    action_by_symbol: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Cost-weighted since-buy mark % by last AI validate action (display only).

    FinRobot + xang1234 Group Matrix + portfolio AI: lots whose newest
    debate was BUY / HOLD / SELL vs no memory (none). ``action_by_symbol``
    None → skip (caller did not wire). Empty map → all none. Cluster n on
    labels. Strip only; not a gate; not a research score.
    """
    bands: dict[str, dict[str, Any]] = {
        "buy": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "hold": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "sell": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "none": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
    }
    out: dict[str, Any] = {
        "ai_debate_buy_pct": None,
        "ai_debate_hold_pct": None,
        "ai_debate_sell_pct": None,
        "ai_debate_none_pct": None,
        "ai_debate_buy_label": "",
        "ai_debate_hold_label": "",
        "ai_debate_sell_label": "",
        "ai_debate_none_label": "",
        "ai_debate_buy_lots": 0,
        "ai_debate_hold_lots": 0,
        "ai_debate_sell_lots": 0,
        "ai_debate_none_lots": 0,
        "ai_debate_marks_ready": False,
        "ai_debate_marks_bit": "",
    }
    if action_by_symbol is None:
        return out

    actions: dict[str, str] = {}
    for raw_sym, raw_act in action_by_symbol.items():
        sym = str(raw_sym or "").strip().upper()
        if not sym:
            continue
        act = str(raw_act or "HOLD").upper()
        if act not in {"BUY", "SELL", "HOLD"}:
            act = "HOLD"
        actions[sym] = act

    for h in holdings:
        if not isinstance(h, dict):
            continue
        basis = _holding_cost_basis(h)
        if basis <= 0:
            continue
        sym = str(h.get("symbol") or "").strip().upper()
        if not sym:
            continue
        act = actions.get(sym)
        key = "none" if act is None else act.lower()
        bucket = bands[key]
        bucket["lots"] += 1
        pct = _holding_marked_pct(h)
        if pct is None:
            continue
        bucket["marked"] += 1
        bucket["cost"] += basis
        bucket["w_pct"] += basis * pct

    bits: list[str] = []
    for key, short, field in (
        ("buy", "buy", "ai_debate_buy"),
        ("hold", "hold", "ai_debate_hold"),
        ("sell", "sell", "ai_debate_sell"),
        ("none", "none", "ai_debate_none"),
    ):
        bucket = bands[key]
        has_lots = int(bucket["lots"]) > 0
        any_marked = int(bucket["marked"]) > 0
        pct: float | None = None
        if any_marked and float(bucket["cost"]) > 0:
            pct = float(bucket["w_pct"]) / float(bucket["cost"])
        cluster_n = int(bucket["marked"] if any_marked else bucket["lots"])
        label = _format_mark_pct(
            pct, has_lots=has_lots, any_marked=any_marked, cluster_n=cluster_n
        )
        out[f"{field}_lots"] = int(bucket["lots"])
        out[f"{field}_pct"] = round(pct, 2) if pct is not None else None
        out[f"{field}_label"] = label
        if label:
            bits.append(f"{short} {label}")
    if bits:
        out["ai_debate_marks_ready"] = True
        out["ai_debate_marks_bit"] = "ai " + " · ".join(bits)
    return out


def ai_confidence_mark_returns(
    holdings: list[dict[str, Any]],
    confidence_by_symbol: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Cost-weighted since-buy mark % by last AI validate confidence (display only).

    FinRobot + xang1234 Group Matrix + portfolio AI: lots whose newest
    debate was HIGH / MEDIUM / LOW vs no memory (none).
    ``confidence_by_symbol`` None → skip (caller did not wire). Empty map
    → all none. Cluster n on labels. Strip only; not a gate; not a
    research score.
    """
    bands: dict[str, dict[str, Any]] = {
        "high": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "med": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "low": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "none": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
    }
    out: dict[str, Any] = {
        "ai_conf_high_pct": None,
        "ai_conf_med_pct": None,
        "ai_conf_low_pct": None,
        "ai_conf_none_pct": None,
        "ai_conf_high_label": "",
        "ai_conf_med_label": "",
        "ai_conf_low_label": "",
        "ai_conf_none_label": "",
        "ai_conf_high_lots": 0,
        "ai_conf_med_lots": 0,
        "ai_conf_low_lots": 0,
        "ai_conf_none_lots": 0,
        "ai_conf_marks_ready": False,
        "ai_conf_marks_bit": "",
    }
    if confidence_by_symbol is None:
        return out

    confs: dict[str, str] = {}
    for raw_sym, raw_conf in confidence_by_symbol.items():
        sym = str(raw_sym or "").strip().upper()
        if not sym:
            continue
        conf = str(raw_conf or "").upper()
        if conf == "MEDIUM":
            conf = "MED"
        if conf not in {"HIGH", "MED", "LOW"}:
            continue
        confs[sym] = conf

    for h in holdings:
        if not isinstance(h, dict):
            continue
        basis = _holding_cost_basis(h)
        if basis <= 0:
            continue
        sym = str(h.get("symbol") or "").strip().upper()
        if not sym:
            continue
        conf = confs.get(sym)
        key = "none" if conf is None else conf.lower()
        bucket = bands[key]
        bucket["lots"] += 1
        pct = _holding_marked_pct(h)
        if pct is None:
            continue
        bucket["marked"] += 1
        bucket["cost"] += basis
        bucket["w_pct"] += basis * pct

    bits: list[str] = []
    for key, short, field in (
        ("high", "hi", "ai_conf_high"),
        ("med", "med", "ai_conf_med"),
        ("low", "lo", "ai_conf_low"),
        ("none", "none", "ai_conf_none"),
    ):
        bucket = bands[key]
        has_lots = int(bucket["lots"]) > 0
        any_marked = int(bucket["marked"]) > 0
        pct: float | None = None
        if any_marked and float(bucket["cost"]) > 0:
            pct = float(bucket["w_pct"]) / float(bucket["cost"])
        cluster_n = int(bucket["marked"] if any_marked else bucket["lots"])
        label = _format_mark_pct(
            pct, has_lots=has_lots, any_marked=any_marked, cluster_n=cluster_n
        )
        out[f"{field}_lots"] = int(bucket["lots"])
        out[f"{field}_pct"] = round(pct, 2) if pct is not None else None
        out[f"{field}_label"] = label
        if label:
            bits.append(f"{short} {label}")
    if bits:
        out["ai_conf_marks_ready"] = True
        out["ai_conf_marks_bit"] = "conf " + " · ".join(bits)
    return out


def ai_gated_mark_returns(
    holdings: list[dict[str, Any]],
    gated_by_symbol: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """Cost-weighted since-buy mark % by last multi-role veto (display only).

    FinRobot + xang1234 Group Matrix + portfolio AI: lots whose newest
    debate was role-gated (veto→HOLD) vs free vs no memory (none).
    ``gated_by_symbol`` None → skip (caller did not wire). Empty map →
    all none. Cluster n on labels. Strip only; not a gate; not a
    research score.
    """
    bands: dict[str, dict[str, Any]] = {
        "gated": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "free": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "none": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
    }
    out: dict[str, Any] = {
        "ai_roles_gated_pct": None,
        "ai_roles_free_pct": None,
        "ai_roles_none_pct": None,
        "ai_roles_gated_label": "",
        "ai_roles_free_label": "",
        "ai_roles_none_label": "",
        "ai_roles_gated_lots": 0,
        "ai_roles_free_lots": 0,
        "ai_roles_none_lots": 0,
        "ai_roles_marks_ready": False,
        "ai_roles_marks_bit": "",
    }
    if gated_by_symbol is None:
        return out

    flags: dict[str, bool] = {}
    for raw_sym, raw_flag in gated_by_symbol.items():
        sym = str(raw_sym or "").strip().upper()
        if not sym:
            continue
        flags[sym] = bool(raw_flag)

    for h in holdings:
        if not isinstance(h, dict):
            continue
        basis = _holding_cost_basis(h)
        if basis <= 0:
            continue
        sym = str(h.get("symbol") or "").strip().upper()
        if not sym:
            continue
        if sym not in flags:
            key = "none"
        else:
            key = "gated" if flags[sym] else "free"
        bucket = bands[key]
        bucket["lots"] += 1
        pct = _holding_marked_pct(h)
        if pct is None:
            continue
        bucket["marked"] += 1
        bucket["cost"] += basis
        bucket["w_pct"] += basis * pct

    bits: list[str] = []
    for key, short, field in (
        ("gated", "gated", "ai_roles_gated"),
        ("free", "free", "ai_roles_free"),
        ("none", "none", "ai_roles_none"),
    ):
        bucket = bands[key]
        has_lots = int(bucket["lots"]) > 0
        any_marked = int(bucket["marked"]) > 0
        pct: float | None = None
        if any_marked and float(bucket["cost"]) > 0:
            pct = float(bucket["w_pct"]) / float(bucket["cost"])
        cluster_n = int(bucket["marked"] if any_marked else bucket["lots"])
        label = _format_mark_pct(
            pct, has_lots=has_lots, any_marked=any_marked, cluster_n=cluster_n
        )
        out[f"{field}_lots"] = int(bucket["lots"])
        out[f"{field}_pct"] = round(pct, 2) if pct is not None else None
        out[f"{field}_label"] = label
        if label:
            bits.append(f"{short} {label}")
    if bits:
        out["ai_roles_marks_ready"] = True
        out["ai_roles_marks_bit"] = "roles " + " · ".join(bits)
    return out


def scan_vol_mark_returns(
    holdings: list[dict[str, Any]],
    has_vol_by_symbol: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """Cost-weighted since-buy mark % by Screener ATR/vol note (display only).

    staskh + RyanJHamby + xang1234 Group Matrix: lots with a usable stop
    note (with) vs soft n/a on the scan map (soft) vs off-list. Prefer
    ``True`` when a symbol appears on multiple lists. ``has_vol_by_symbol``
    None → skip. Empty map → all off. Cluster n on labels. Strip only;
    not a gate; live TP/SL stay exit_policy.
    """
    bands: dict[str, dict[str, Any]] = {
        "with": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "soft": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
        "off": {"cost": 0.0, "w_pct": 0.0, "lots": 0, "marked": 0},
    }
    out: dict[str, Any] = {
        "scan_vol_with_pct": None,
        "scan_vol_soft_pct": None,
        "scan_vol_off_pct": None,
        "scan_vol_with_label": "",
        "scan_vol_soft_label": "",
        "scan_vol_off_label": "",
        "scan_vol_with_lots": 0,
        "scan_vol_soft_lots": 0,
        "scan_vol_off_lots": 0,
        "scan_vol_marks_ready": False,
        "scan_vol_marks_bit": "",
    }
    if has_vol_by_symbol is None:
        return out

    flags: dict[str, bool] = {}
    for raw_sym, raw_flag in has_vol_by_symbol.items():
        sym = str(raw_sym or "").strip().upper()
        if not sym:
            continue
        flag = bool(raw_flag)
        # Prefer has-vol when the name appears on multiple lists.
        if sym not in flags or flag:
            flags[sym] = flag

    for h in holdings:
        if not isinstance(h, dict):
            continue
        basis = _holding_cost_basis(h)
        if basis <= 0:
            continue
        sym = str(h.get("symbol") or "").strip().upper()
        if not sym:
            continue
        if sym not in flags:
            key = "off"
        else:
            key = "with" if flags[sym] else "soft"
        bucket = bands[key]
        bucket["lots"] += 1
        pct = _holding_marked_pct(h)
        if pct is None:
            continue
        bucket["marked"] += 1
        bucket["cost"] += basis
        bucket["w_pct"] += basis * pct

    bits: list[str] = []
    for key, short, field in (
        ("with", "with", "scan_vol_with"),
        ("soft", "soft", "scan_vol_soft"),
        ("off", "off", "scan_vol_off"),
    ):
        bucket = bands[key]
        has_lots = int(bucket["lots"]) > 0
        any_marked = int(bucket["marked"]) > 0
        pct: float | None = None
        if any_marked and float(bucket["cost"]) > 0:
            pct = float(bucket["w_pct"]) / float(bucket["cost"])
        cluster_n = int(bucket["marked"] if any_marked else bucket["lots"])
        label = _format_mark_pct(
            pct, has_lots=has_lots, any_marked=any_marked, cluster_n=cluster_n
        )
        out[f"{field}_lots"] = int(bucket["lots"])
        out[f"{field}_pct"] = round(pct, 2) if pct is not None else None
        out[f"{field}_label"] = label
        if label:
            bits.append(f"{short} {label}")
    if bits:
        out["scan_vol_marks_ready"] = True
        out["scan_vol_marks_bit"] = "vol " + " · ".join(bits)
    return out


def book_risk_report(
    *,
    cash: float,
    equity: float,
    holdings: list[dict[str, Any]],
    max_positions: int = 5,
    max_name_pct: float = DEFAULT_MAX_NAME_PCT,
    min_hold_seconds: float | None = None,
    scan_symbols: Iterable[str] | None = None,
    scan_leaders: Iterable[str] | None = None,
    scan_breakouts: Iterable[str] | None = None,
    scan_recommendations: Iterable[str] | None = None,
    scan_scores: dict[str, float] | None = None,
    scan_pct_from_high: dict[str, float] | None = None,
    scan_change_24h: dict[str, float] | None = None,
    scan_has_vol: dict[str, bool] | None = None,
    ai_actions: dict[str, str] | None = None,
    ai_confidences: dict[str, str] | None = None,
    ai_gated: dict[str, bool] | None = None,
    trades: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Display-only book risk strip (staskh / portfolio-AI style).

    Cash %, slots, posture, largest name, equity vs crypto mix,
    sleeve + venue + exit-band + min-hold lock + entry session
    (wd Mon–Fri UTC / we Sat–Sun) + entry hours (cash open / AH /
    crypto 24/7) + entry rebuy vs fresh (prior SELL in trades) +
    entry rebuy gap fast/cool/fresh (inside vs after anti-flip-flop
    cooldown) + entry post-SL vs other exit vs fresh (revenge-refill
    honesty) + entry post-TP vs other vs fresh + entry buy-source
    scan/rebal/other/none + entry buy-score hi/mid/lo/none + soft
    concentration cap at/under + scan membership + screener list
    role (lead/brk/rec/off) + scan score bands (hi/mid/lo/off) +
    pct_from_high near/mid/deep/off + day-change hot/cold/quiet/off
    (±4% StockBee) + ATR vol with/soft/off + AI debate action + AI
    confidence + multi-role gated + hold-tenure + win/lose polarity
    + size + leader mark returns (Group Matrix–lite, cluster n on
    labels). Does not change entries or exits.
    """
    from stock_checker.exit_policy import book_action_mode

    empty_marks = {
        "equity_mark_pct": None,
        "crypto_mark_pct": None,
        "equity_mark_label": "",
        "crypto_mark_label": "",
        "sleeve_marks_ready": False,
        "sleeve_marks_bit": "",
        "equity_lots": 0,
        "crypto_lots": 0,
        "equity_marked": 0,
        "crypto_marked": 0,
        "tenure_lt_7d_pct": None,
        "tenure_7_30d_pct": None,
        "tenure_ge_30d_pct": None,
        "tenure_lt_7d_label": "",
        "tenure_7_30d_label": "",
        "tenure_ge_30d_label": "",
        "tenure_marks_ready": False,
        "tenure_marks_bit": "",
        "tenure_unknown_lots": 0,
        "tenure_lt_7d_lots": 0,
        "tenure_7_30d_lots": 0,
        "tenure_ge_30d_lots": 0,
        "polarity_win_pct": None,
        "polarity_lose_pct": None,
        "polarity_win_label": "",
        "polarity_lose_label": "",
        "polarity_win_lots": 0,
        "polarity_lose_lots": 0,
        "polarity_flat_lots": 0,
        "polarity_unmarked_lots": 0,
        "polarity_marks_ready": False,
        "polarity_marks_bit": "",
        "size_large_pct": None,
        "size_small_pct": None,
        "size_large_label": "",
        "size_small_label": "",
        "size_large_lots": 0,
        "size_small_lots": 0,
        "size_marks_ready": False,
        "size_marks_bit": "",
        "leader_symbol": "",
        "leader_mark_pct": None,
        "leader_rest_pct": None,
        "leader_mark_label": "",
        "leader_rest_label": "",
        "leader_lots": 0,
        "leader_rest_lots": 0,
        "leader_marks_ready": False,
        "leader_marks_bit": "",
        "leader_cost_share": 0.0,
        "venue_us_pct": None,
        "venue_xetra_pct": None,
        "venue_crypto_pct": None,
        "venue_us_label": "",
        "venue_xetra_label": "",
        "venue_crypto_label": "",
        "venue_us_lots": 0,
        "venue_xetra_lots": 0,
        "venue_crypto_lots": 0,
        "venue_marks_ready": False,
        "venue_marks_bit": "",
        "exit_band_tp_pct": None,
        "exit_band_mid_pct": None,
        "exit_band_sl_pct": None,
        "exit_band_tp_label": "",
        "exit_band_mid_label": "",
        "exit_band_sl_label": "",
        "exit_band_tp_lots": 0,
        "exit_band_mid_lots": 0,
        "exit_band_sl_lots": 0,
        "exit_band_unmarked_lots": 0,
        "exit_band_marks_ready": False,
        "exit_band_marks_bit": "",
        "exit_band_zone_frac": float(EXIT_BAND_ZONE_FRAC),
        "live_rr_ok_pct": None,
        "live_rr_thin_pct": None,
        "live_rr_hit_pct": None,
        "live_rr_ok_label": "",
        "live_rr_thin_label": "",
        "live_rr_hit_label": "",
        "live_rr_ok_lots": 0,
        "live_rr_thin_lots": 0,
        "live_rr_hit_lots": 0,
        "live_rr_unknown_lots": 0,
        "live_rr_stock_designed": None,
        "live_rr_crypto_designed": None,
        "live_rr_marks_ready": False,
        "live_rr_marks_bit": "",
        "min_hold_lock_pct": None,
        "min_hold_free_pct": None,
        "min_hold_lock_label": "",
        "min_hold_free_label": "",
        "min_hold_lock_lots": 0,
        "min_hold_free_lots": 0,
        "min_hold_unknown_lots": 0,
        "min_hold_marks_ready": False,
        "min_hold_marks_bit": "",
        "entry_session_wd_pct": None,
        "entry_session_we_pct": None,
        "entry_session_wd_label": "",
        "entry_session_we_label": "",
        "entry_session_wd_lots": 0,
        "entry_session_we_lots": 0,
        "entry_session_unknown_lots": 0,
        "entry_session_marks_ready": False,
        "entry_session_marks_bit": "",
        "entry_hours_open_pct": None,
        "entry_hours_closed_pct": None,
        "entry_hours_cr_pct": None,
        "entry_hours_open_label": "",
        "entry_hours_closed_label": "",
        "entry_hours_cr_label": "",
        "entry_hours_open_lots": 0,
        "entry_hours_closed_lots": 0,
        "entry_hours_cr_lots": 0,
        "entry_hours_unknown_lots": 0,
        "entry_hours_marks_ready": False,
        "entry_hours_marks_bit": "",
        "entry_rebuy_rebuy_pct": None,
        "entry_rebuy_fresh_pct": None,
        "entry_rebuy_rebuy_label": "",
        "entry_rebuy_fresh_label": "",
        "entry_rebuy_rebuy_lots": 0,
        "entry_rebuy_fresh_lots": 0,
        "entry_rebuy_unknown_lots": 0,
        "entry_rebuy_marks_ready": False,
        "entry_rebuy_marks_bit": "",
        "entry_rebuy_gap_fast_pct": None,
        "entry_rebuy_gap_cool_pct": None,
        "entry_rebuy_gap_fresh_pct": None,
        "entry_rebuy_gap_fast_label": "",
        "entry_rebuy_gap_cool_label": "",
        "entry_rebuy_gap_fresh_label": "",
        "entry_rebuy_gap_fast_lots": 0,
        "entry_rebuy_gap_cool_lots": 0,
        "entry_rebuy_gap_fresh_lots": 0,
        "entry_rebuy_gap_unknown_lots": 0,
        "entry_rebuy_gap_marks_ready": False,
        "entry_rebuy_gap_marks_bit": "",
        "entry_rebuy_gap_cooldown_sec": float(DEFAULT_REBUY_COOLDOWN_SEC),
        "entry_post_sl_sl_pct": None,
        "entry_post_sl_oth_pct": None,
        "entry_post_sl_fresh_pct": None,
        "entry_post_sl_sl_label": "",
        "entry_post_sl_oth_label": "",
        "entry_post_sl_fresh_label": "",
        "entry_post_sl_sl_lots": 0,
        "entry_post_sl_oth_lots": 0,
        "entry_post_sl_fresh_lots": 0,
        "entry_post_sl_unknown_lots": 0,
        "entry_post_sl_marks_ready": False,
        "entry_post_sl_marks_bit": "",
        "entry_post_tp_tp_pct": None,
        "entry_post_tp_oth_pct": None,
        "entry_post_tp_fresh_pct": None,
        "entry_post_tp_tp_label": "",
        "entry_post_tp_oth_label": "",
        "entry_post_tp_fresh_label": "",
        "entry_post_tp_tp_lots": 0,
        "entry_post_tp_oth_lots": 0,
        "entry_post_tp_fresh_lots": 0,
        "entry_post_tp_unknown_lots": 0,
        "entry_post_tp_marks_ready": False,
        "entry_post_tp_marks_bit": "",
        "entry_post_rot_rot_pct": None,
        "entry_post_rot_oth_pct": None,
        "entry_post_rot_fresh_pct": None,
        "entry_post_rot_rot_label": "",
        "entry_post_rot_oth_label": "",
        "entry_post_rot_fresh_label": "",
        "entry_post_rot_rot_lots": 0,
        "entry_post_rot_oth_lots": 0,
        "entry_post_rot_fresh_lots": 0,
        "entry_post_rot_unknown_lots": 0,
        "entry_post_rot_marks_ready": False,
        "entry_post_rot_marks_bit": "",
        "entry_post_trim_trim_pct": None,
        "entry_post_trim_oth_pct": None,
        "entry_post_trim_fresh_pct": None,
        "entry_post_trim_trim_label": "",
        "entry_post_trim_oth_label": "",
        "entry_post_trim_fresh_label": "",
        "entry_post_trim_trim_lots": 0,
        "entry_post_trim_oth_lots": 0,
        "entry_post_trim_fresh_lots": 0,
        "entry_post_trim_unknown_lots": 0,
        "entry_post_trim_marks_ready": False,
        "entry_post_trim_marks_bit": "",
        "entry_buy_fee_free_pct": None,
        "entry_buy_fee_paid_pct": None,
        "entry_buy_fee_free_label": "",
        "entry_buy_fee_paid_label": "",
        "entry_buy_fee_free_lots": 0,
        "entry_buy_fee_paid_lots": 0,
        "entry_buy_fee_unknown_lots": 0,
        "entry_buy_fee_marks_ready": False,
        "entry_buy_fee_marks_bit": "",
        "entry_buy_conf_hi_pct": None,
        "entry_buy_conf_med_pct": None,
        "entry_buy_conf_lo_pct": None,
        "entry_buy_conf_none_pct": None,
        "entry_buy_conf_hi_label": "",
        "entry_buy_conf_med_label": "",
        "entry_buy_conf_lo_label": "",
        "entry_buy_conf_none_label": "",
        "entry_buy_conf_hi_lots": 0,
        "entry_buy_conf_med_lots": 0,
        "entry_buy_conf_lo_lots": 0,
        "entry_buy_conf_none_lots": 0,
        "entry_buy_conf_unknown_lots": 0,
        "entry_buy_conf_marks_ready": False,
        "entry_buy_conf_marks_bit": "",
        "entry_buy_src_scan_pct": None,
        "entry_buy_src_rebal_pct": None,
        "entry_buy_src_other_pct": None,
        "entry_buy_src_none_pct": None,
        "entry_buy_src_scan_label": "",
        "entry_buy_src_rebal_label": "",
        "entry_buy_src_other_label": "",
        "entry_buy_src_none_label": "",
        "entry_buy_src_scan_lots": 0,
        "entry_buy_src_rebal_lots": 0,
        "entry_buy_src_other_lots": 0,
        "entry_buy_src_none_lots": 0,
        "entry_buy_src_unknown_lots": 0,
        "entry_buy_src_marks_ready": False,
        "entry_buy_src_marks_bit": "",
        "entry_buy_score_hi_pct": None,
        "entry_buy_score_mid_pct": None,
        "entry_buy_score_lo_pct": None,
        "entry_buy_score_none_pct": None,
        "entry_buy_score_hi_label": "",
        "entry_buy_score_mid_label": "",
        "entry_buy_score_lo_label": "",
        "entry_buy_score_none_label": "",
        "entry_buy_score_hi_lots": 0,
        "entry_buy_score_mid_lots": 0,
        "entry_buy_score_lo_lots": 0,
        "entry_buy_score_none_lots": 0,
        "entry_buy_score_unknown_lots": 0,
        "entry_buy_score_marks_ready": False,
        "entry_buy_score_marks_bit": "",
        "entry_buy_score_hi_floor": float(SCAN_SCORE_HI),
        "entry_buy_score_mid_floor": float(SCAN_SCORE_MID),
        "entry_buy_strat_brk_pct": None,
        "entry_buy_strat_mom_pct": None,
        "entry_buy_strat_oth_pct": None,
        "entry_buy_strat_none_pct": None,
        "entry_buy_strat_brk_label": "",
        "entry_buy_strat_mom_label": "",
        "entry_buy_strat_oth_label": "",
        "entry_buy_strat_none_label": "",
        "entry_buy_strat_brk_lots": 0,
        "entry_buy_strat_mom_lots": 0,
        "entry_buy_strat_oth_lots": 0,
        "entry_buy_strat_none_lots": 0,
        "entry_buy_strat_unknown_lots": 0,
        "entry_buy_strat_marks_ready": False,
        "entry_buy_strat_marks_bit": "",
        "entry_buy_size_fat_pct": None,
        "entry_buy_size_ok_pct": None,
        "entry_buy_size_thin_pct": None,
        "entry_buy_size_none_pct": None,
        "entry_buy_size_fat_label": "",
        "entry_buy_size_ok_label": "",
        "entry_buy_size_thin_label": "",
        "entry_buy_size_none_label": "",
        "entry_buy_size_fat_lots": 0,
        "entry_buy_size_ok_lots": 0,
        "entry_buy_size_thin_lots": 0,
        "entry_buy_size_none_lots": 0,
        "entry_buy_size_unknown_lots": 0,
        "entry_buy_size_marks_ready": False,
        "entry_buy_size_marks_bit": "",
        "entry_buy_size_default_frac": float(DEFAULT_ENTRY_CASH_FRAC),
        "entry_buy_size_fat_floor": float(ENTRY_SIZE_FAT_FRAC),
        "entry_buy_size_thin_floor": float(ENTRY_SIZE_THIN_FRAC),
        "entry_conc_at_pct": None,
        "entry_conc_under_pct": None,
        "entry_conc_at_label": "",
        "entry_conc_under_label": "",
        "entry_conc_at_lots": 0,
        "entry_conc_under_lots": 0,
        "entry_conc_unknown_lots": 0,
        "entry_conc_cap_pct": float(DEFAULT_MAX_NAME_PCT),
        "entry_conc_marks_ready": False,
        "entry_conc_marks_bit": "",
        "scan_on_pct": None,
        "scan_off_pct": None,
        "scan_on_label": "",
        "scan_off_label": "",
        "scan_on_lots": 0,
        "scan_off_lots": 0,
        "scan_marks_ready": False,
        "scan_marks_bit": "",
        "scan_list_lead_pct": None,
        "scan_list_brk_pct": None,
        "scan_list_rec_pct": None,
        "scan_list_off_pct": None,
        "scan_list_lead_label": "",
        "scan_list_brk_label": "",
        "scan_list_rec_label": "",
        "scan_list_off_label": "",
        "scan_list_lead_lots": 0,
        "scan_list_brk_lots": 0,
        "scan_list_rec_lots": 0,
        "scan_list_off_lots": 0,
        "scan_list_marks_ready": False,
        "scan_list_marks_bit": "",
        "scan_score_hi_pct": None,
        "scan_score_mid_pct": None,
        "scan_score_lo_pct": None,
        "scan_score_off_pct": None,
        "scan_score_hi_label": "",
        "scan_score_mid_label": "",
        "scan_score_lo_label": "",
        "scan_score_off_label": "",
        "scan_score_hi_lots": 0,
        "scan_score_mid_lots": 0,
        "scan_score_lo_lots": 0,
        "scan_score_off_lots": 0,
        "scan_score_marks_ready": False,
        "scan_score_marks_bit": "",
        "scan_score_hi_floor": float(SCAN_SCORE_HI),
        "scan_score_mid_floor": float(SCAN_SCORE_MID),
        "scan_near_high_near_pct": None,
        "scan_near_high_mid_pct": None,
        "scan_near_high_deep_pct": None,
        "scan_near_high_off_pct": None,
        "scan_near_high_near_label": "",
        "scan_near_high_mid_label": "",
        "scan_near_high_deep_label": "",
        "scan_near_high_off_label": "",
        "scan_near_high_near_lots": 0,
        "scan_near_high_mid_lots": 0,
        "scan_near_high_deep_lots": 0,
        "scan_near_high_off_lots": 0,
        "scan_near_high_marks_ready": False,
        "scan_near_high_marks_bit": "",
        "scan_near_high_floor": float(SCAN_NEAR_HIGH_PCT),
        "scan_near_high_mid_floor": float(SCAN_NEAR_HIGH_MID),
        "scan_mover_hot_pct": None,
        "scan_mover_cold_pct": None,
        "scan_mover_quiet_pct": None,
        "scan_mover_off_pct": None,
        "scan_mover_hot_label": "",
        "scan_mover_cold_label": "",
        "scan_mover_quiet_label": "",
        "scan_mover_off_label": "",
        "scan_mover_hot_lots": 0,
        "scan_mover_cold_lots": 0,
        "scan_mover_quiet_lots": 0,
        "scan_mover_off_lots": 0,
        "scan_mover_marks_ready": False,
        "scan_mover_marks_bit": "",
        "scan_mover_floor": float(SCAN_MOVER_PCT),
        "scan_vol_with_pct": None,
        "scan_vol_soft_pct": None,
        "scan_vol_off_pct": None,
        "scan_vol_with_label": "",
        "scan_vol_soft_label": "",
        "scan_vol_off_label": "",
        "scan_vol_with_lots": 0,
        "scan_vol_soft_lots": 0,
        "scan_vol_off_lots": 0,
        "scan_vol_marks_ready": False,
        "scan_vol_marks_bit": "",
        "ai_debate_buy_pct": None,
        "ai_debate_hold_pct": None,
        "ai_debate_sell_pct": None,
        "ai_debate_none_pct": None,
        "ai_debate_buy_label": "",
        "ai_debate_hold_label": "",
        "ai_debate_sell_label": "",
        "ai_debate_none_label": "",
        "ai_debate_buy_lots": 0,
        "ai_debate_hold_lots": 0,
        "ai_debate_sell_lots": 0,
        "ai_debate_none_lots": 0,
        "ai_debate_marks_ready": False,
        "ai_debate_marks_bit": "",
        "ai_conf_high_pct": None,
        "ai_conf_med_pct": None,
        "ai_conf_low_pct": None,
        "ai_conf_none_pct": None,
        "ai_conf_high_label": "",
        "ai_conf_med_label": "",
        "ai_conf_low_label": "",
        "ai_conf_none_label": "",
        "ai_conf_high_lots": 0,
        "ai_conf_med_lots": 0,
        "ai_conf_low_lots": 0,
        "ai_conf_none_lots": 0,
        "ai_conf_marks_ready": False,
        "ai_conf_marks_bit": "",
        "ai_roles_gated_pct": None,
        "ai_roles_free_pct": None,
        "ai_roles_none_pct": None,
        "ai_roles_gated_label": "",
        "ai_roles_free_label": "",
        "ai_roles_none_label": "",
        "ai_roles_gated_lots": 0,
        "ai_roles_free_lots": 0,
        "ai_roles_none_lots": 0,
        "ai_roles_marks_ready": False,
        "ai_roles_marks_bit": "",
    }
    try:
        cash_f = float(cash)
        equity_f = float(equity)
        max_n = int(max_positions)
        cap_pct = abs(float(max_name_pct))
    except (TypeError, ValueError):
        return {
            "cash_pct": 0.0,
            "slots": "0/5",
            "open_positions": 0,
            "max_positions": 5,
            "posture": "open",
            "largest_symbol": "",
            "largest_pct": 0.0,
            "equity_pct": 0.0,
            "crypto_pct": 0.0,
            "concentration_warn": False,
            "note": "unreadable book inputs",
            **empty_marks,
        }

    if max_n < 1:
        max_n = 1
    hold_s: float | None = None
    if min_hold_seconds is not None:
        try:
            hold_s = max(0.0, float(min_hold_seconds))
        except (TypeError, ValueError):
            hold_s = None
    rows = [h for h in holdings if isinstance(h, dict)]
    open_n = len(rows)
    posture = book_action_mode(open_n, max_n)
    cash_pct = (cash_f / equity_f * 100.0) if equity_f > 0 else 0.0

    largest_symbol = ""
    largest_pct = 0.0
    equity_mv = 0.0
    crypto_mv = 0.0
    for h in rows:
        try:
            mv = float(h.get("market_value") or 0.0)
        except (TypeError, ValueError):
            mv = 0.0
        sym = str(h.get("symbol") or "")
        kind = str(h.get("kind") or "")
        if not kind:
            kind = "crypto" if "-USD" in sym else "stock"
        if kind == "crypto":
            crypto_mv += mv
        else:
            equity_mv += mv
        w = (mv / equity_f * 100.0) if equity_f > 0 else 0.0
        if w > largest_pct:
            largest_pct = w
            largest_symbol = sym

    invested = equity_mv + crypto_mv
    if invested > 0:
        eq_share = equity_mv / invested * 100.0
        cr_share = crypto_mv / invested * 100.0
    else:
        eq_share = 0.0
        cr_share = 0.0

    marks = sleeve_mark_returns(rows)
    tenure = tenure_mark_returns(rows)
    polarity = polarity_mark_returns(rows)
    size = size_mark_returns(rows)
    leader = leader_mark_returns(rows)
    venue = venue_mark_returns(rows)
    exit_band = exit_band_mark_returns(rows)
    live_rr = live_rr_mark_returns(rows)
    min_hold = min_hold_mark_returns(rows, min_hold_seconds=hold_s)
    entry_session = entry_session_mark_returns(rows)
    entry_hours = entry_hours_mark_returns(rows)
    entry_rebuy = entry_rebuy_mark_returns(rows, trades)
    entry_rebuy_gap = entry_rebuy_gap_mark_returns(
        rows,
        trades,
        cooldown_seconds=(
            hold_s if hold_s is not None else float(DEFAULT_REBUY_COOLDOWN_SEC)
        ),
    )
    entry_post_sl = entry_post_sl_mark_returns(rows, trades)
    entry_post_tp = entry_post_tp_mark_returns(rows, trades)
    entry_post_rot = entry_post_rotation_mark_returns(rows, trades)
    entry_post_trim = entry_post_trim_mark_returns(rows, trades)
    entry_buy_fee = entry_buy_fee_mark_returns(rows, trades)
    entry_buy_conf = entry_buy_confidence_mark_returns(rows, trades)
    entry_buy_src = entry_buy_source_mark_returns(rows, trades)
    entry_buy_score = entry_buy_score_mark_returns(rows, trades)
    entry_buy_strat = entry_buy_strategy_mark_returns(rows, trades)
    entry_buy_size = entry_buy_size_mark_returns(rows, trades)
    entry_conc = entry_concentration_mark_returns(
        rows, equity=equity_f, max_name_pct=cap_pct
    )
    scan = scan_mark_returns(rows, scan_symbols)
    scan_list = scan_list_mark_returns(
        rows,
        leaders=scan_leaders,
        breakouts=scan_breakouts,
        recommendations=scan_recommendations,
    )
    scan_score = scan_score_mark_returns(rows, scan_scores)
    scan_near = scan_near_high_mark_returns(rows, scan_pct_from_high)
    scan_mover = scan_mover_mark_returns(rows, scan_change_24h)
    scan_vol = scan_vol_mark_returns(rows, scan_has_vol)
    ai_debate = ai_debate_mark_returns(rows, ai_actions)
    ai_conf = ai_confidence_mark_returns(rows, ai_confidences)
    ai_roles = ai_gated_mark_returns(rows, ai_gated)
    concentration_warn = bool(largest_symbol) and largest_pct >= cap_pct
    bits = [f"{open_n}/{max_n} slots · {posture}"]
    if largest_symbol:
        bits.append(f"largest {largest_symbol} {largest_pct:.0f}%")
    bits.append(f"cash {cash_pct:.0f}%")
    if invested > 0:
        bits.append(f"mix equity {eq_share:.0f}% / crypto {cr_share:.0f}%")
    if marks.get("sleeve_marks_bit"):
        bits.append(str(marks["sleeve_marks_bit"]))
    if concentration_warn:
        bits.append(f"≥{cap_pct:g}% name weight")

    return {
        "cash_pct": round(cash_pct, 1),
        "slots": f"{open_n}/{max_n}",
        "open_positions": open_n,
        "max_positions": max_n,
        "posture": posture,
        "largest_symbol": largest_symbol,
        "largest_pct": round(largest_pct, 1),
        "equity_pct": round(eq_share, 1),
        "crypto_pct": round(cr_share, 1),
        "concentration_warn": concentration_warn,
        "note": " · ".join(bits),
        **marks,
        **tenure,
        **polarity,
        **size,
        **leader,
        **venue,
        **exit_band,
        **live_rr,
        **min_hold,
        **entry_session,
        **entry_hours,
        **entry_rebuy,
        **entry_rebuy_gap,
        **entry_post_sl,
        **entry_post_tp,
        **entry_post_rot,
        **entry_post_trim,
        **entry_buy_fee,
        **entry_buy_conf,
        **entry_buy_src,
        **entry_buy_score,
        **entry_buy_strat,
        **entry_buy_size,
        **entry_conc,
        **scan,
        **scan_list,
        **scan_score,
        **scan_near,
        **scan_mover,
        **scan_vol,
        **ai_debate,
        **ai_conf,
        **ai_roles,
    }


def suggest_entry_notional(
    *,
    cash: float,
    equity: float,
    open_positions: int,
    max_positions: int = 5,
    position_size: float = 0.10,
    max_name_pct: float = DEFAULT_MAX_NAME_PCT,
) -> dict[str, Any]:
    """
    Display-only next-buy size (tradermonty-style sizer).

    Matches live defaults: ~10% of cash, capped by concentration vs equity
    and by open book slots. Does not place orders.
    """
    try:
        cash_f = float(cash)
        equity_f = float(equity)
        open_n = int(open_positions)
        max_n = int(max_positions)
        frac = float(position_size)
        cap_pct = abs(float(max_name_pct))
    except (TypeError, ValueError):
        return {
            "eur": 0.0,
            "cash_frac": 0.10,
            "slots_open": 0,
            "capped_by": "unreadable",
            "note": "unreadable book inputs",
        }

    if max_n < 1:
        max_n = 1
    if frac <= 0:
        frac = 0.10
    slots_open = max(0, max_n - max(0, open_n))
    if slots_open <= 0:
        return {
            "eur": 0.0,
            "cash_frac": frac,
            "slots_open": 0,
            "capped_by": "book_full",
            "note": f"book full ({open_n}/{max_n})",
        }
    if cash_f <= 0 or equity_f <= 0:
        return {
            "eur": 0.0,
            "cash_frac": frac,
            "slots_open": slots_open,
            "capped_by": "no_cash",
            "note": "no cash for a new entry",
        }

    from_cash = cash_f * frac
    from_conc = equity_f * (cap_pct / 100.0)
    eur = min(from_cash, from_conc, cash_f)
    if eur <= 0:
        return {
            "eur": 0.0,
            "cash_frac": frac,
            "slots_open": slots_open,
            "capped_by": "no_cash",
            "note": "no cash for a new entry",
        }
    if from_conc < from_cash:
        capped_by = "concentration"
        note = f"~{frac * 100:.0f}% cash · capped at {cap_pct:g}% equity"
    else:
        capped_by = "cash_frac"
        note = f"~{frac * 100:.0f}% of cash ({slots_open} slot{'s' if slots_open != 1 else ''} open)"
    return {
        "eur": round(eur, 2),
        "cash_frac": frac,
        "slots_open": slots_open,
        "capped_by": capped_by,
        "note": note,
    }


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
    derived = post_sl_buy_block_until(data_dir)
    block_until = max(float(buy_block_until or 0.0), derived)
    if ts < block_until:
        notes.append("post-SL buy cooldown active")
        level = "WARN"

    if not notes:
        notes.append("ok")
    return level, notes

