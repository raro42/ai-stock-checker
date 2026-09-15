"""
Soft risk halts for paper entries (daily loss + concentration).

Does not change exits. Fail-open on unreadable trade logs.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional, Tuple

from stock_checker.market_hours import is_crypto_symbol, is_german_equity

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


def book_risk_report(
    *,
    cash: float,
    equity: float,
    holdings: list[dict[str, Any]],
    max_positions: int = 5,
    max_name_pct: float = DEFAULT_MAX_NAME_PCT,
    min_hold_seconds: float | None = None,
) -> dict[str, Any]:
    """
    Display-only book risk strip (staskh / portfolio-AI style).

    Cash %, slots, posture, largest name, equity vs crypto mix,
    sleeve + venue + exit-band + min-hold lock + hold-tenure + win/lose
    polarity + size + leader mark returns (Group Matrix–lite, cluster n
    on labels). Does not change entries or exits.
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
        "min_hold_lock_pct": None,
        "min_hold_free_pct": None,
        "min_hold_lock_label": "",
        "min_hold_free_label": "",
        "min_hold_lock_lots": 0,
        "min_hold_free_lots": 0,
        "min_hold_unknown_lots": 0,
        "min_hold_marks_ready": False,
        "min_hold_marks_bit": "",
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
    min_hold = min_hold_mark_returns(rows, min_hold_seconds=hold_s)
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
        **min_hold,
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

