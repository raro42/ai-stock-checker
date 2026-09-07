"""Pair paper BUY/SELL fills into closed-round postmortems (desk Book).

Inspired by tradermonty trader-memory / postmortem workflows — local ledger only.
No MAE/MFE without a price path; do not invent excursion stats.
"""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Deque, Mapping, Optional

QTY_EPS = 1e-9
DEFAULT_LIMIT = 12


def _parse_ts(raw: Any) -> Optional[datetime]:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
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


def _hold_label(buy_ts: Any, sell_ts: Any) -> str:
    start = _parse_ts(buy_ts)
    end = _parse_ts(sell_ts)
    if start is None or end is None:
        return ""
    seconds = max(0, int((end - start).total_seconds()))
    if seconds < 3600:
        mins = max(1, seconds // 60) if seconds else 0
        return f"{mins}m"
    hours = seconds / 3600.0
    if hours < 48:
        return f"{hours:.0f}h" if hours >= 10 else f"{hours:.1f}h".rstrip("0").rstrip(".")
    days = hours / 24.0
    return f"{days:.0f}d" if days >= 10 else f"{days:.1f}d".rstrip("0").rstrip(".")


def closed_rounds(
    trades: list[Mapping[str, Any]] | None,
    *,
    limit: int = DEFAULT_LIMIT,
) -> list[dict[str, Any]]:
    """
    FIFO-match BUY lots to SELL fills. Newest closed rounds first.

    Each round: thesis (buy note/strategy) → exit_reason → hold → mark P&L.
    """
    if not trades:
        return []

    opens: dict[str, Deque[dict[str, Any]]] = defaultdict(deque)
    rounds: list[dict[str, Any]] = []

    for raw in trades:
        if not isinstance(raw, Mapping):
            continue
        side = str(raw.get("type") or "").upper()
        sym = str(raw.get("symbol") or "").strip().upper()
        if not sym:
            continue
        try:
            qty = float(raw.get("quantity") or 0)
        except (TypeError, ValueError):
            continue
        if qty <= QTY_EPS:
            continue

        if side == "BUY":
            opens[sym].append(
                {
                    "qty": qty,
                    "price": float(raw.get("price") or 0),
                    "timestamp": raw.get("timestamp") or "",
                    "note": raw.get("note") or "",
                    "strategy": raw.get("strategy") or "",
                    "score": raw.get("score"),
                    "confidence": raw.get("confidence"),
                    "source": raw.get("source") or "",
                }
            )
            continue

        if side != "SELL":
            continue

        sell_price = float(raw.get("price") or 0)
        sell_ts = raw.get("timestamp") or ""
        exit_reason = str(raw.get("exit_reason") or "")[:24]
        sell_note = str(raw.get("note") or "")
        remaining = qty

        while remaining > QTY_EPS and opens[sym]:
            lot = opens[sym][0]
            take = min(lot["qty"], remaining)
            cost = lot["price"] * take
            proceeds = sell_price * take
            pnl = proceeds - cost
            pnl_pct = (pnl / cost) * 100 if cost > QTY_EPS else None

            thesis = str(lot["note"] or "").strip()
            strategy = str(lot["strategy"] or "").strip()
            rounds.append(
                {
                    "symbol": sym,
                    "quantity": take,
                    "buy_price": lot["price"],
                    "sell_price": sell_price,
                    "buy_at": lot["timestamp"],
                    "sell_at": sell_ts,
                    "held": _hold_label(lot["timestamp"], sell_ts),
                    "thesis": thesis,
                    "strategy": strategy,
                    "score": lot.get("score"),
                    "confidence": lot.get("confidence"),
                    "source": lot.get("source") or "",
                    "exit_reason": exit_reason,
                    "exit_note": sell_note,
                    "profit_loss": round(pnl, 4),
                    "profit_loss_pct": None if pnl_pct is None else round(pnl_pct, 2),
                }
            )

            lot["qty"] -= take
            remaining -= take
            if lot["qty"] <= QTY_EPS:
                opens[sym].popleft()

    rounds.reverse()
    if limit > 0:
        return rounds[:limit]
    return rounds
