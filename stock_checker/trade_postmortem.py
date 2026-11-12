"""Pair paper BUY/SELL fills into closed-round postmortems (desk Book).

Inspired by tradermonty trader-memory / postmortem workflows — local ledger only.
No MAE/MFE without a price path; do not invent excursion stats.
SELL qty with no open BUY lot is historical-only (tradermonty #689): speak
``unmatched`` with accounting skipped — never invent long-side P&L.
Missing / non-finite / non-positive prices are unobserved (tradermonty #714):
skip accounting — never invent a flat or −100% mark from empty fills.
"""

from __future__ import annotations

import math
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Deque, Mapping, Optional

QTY_EPS = 1e-9
DEFAULT_LIMIT = 12
# Orphan SELL remainder — long-only book has no open lot to close.
UNMATCHED_SELL_REASON = "unmatched"
UNMATCHED_SELL_NOTE = "No open lot — skipped accounting (long-only)"
# Matched qty but no observed finite buy/sell price — not a measured outcome.
UNOBSERVED_PRICE_REASON = "unobserved"
UNOBSERVED_PRICE_NOTE = "Missing price — skipped accounting (unobserved)"
ACCOUNTING_SKIPPED = "skipped"


def _observed_price(raw: Any) -> Optional[float]:
    """Finite price > 0, else None (do not coerce missing → 0)."""
    if raw is None or raw == "":
        return None
    try:
        price = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(price) or price <= QTY_EPS:
        return None
    return price


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
                    "price": _observed_price(raw.get("price")),
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

        sell_price = _observed_price(raw.get("price"))
        sell_ts = raw.get("timestamp") or ""
        exit_reason = str(raw.get("exit_reason") or "")[:24]
        sell_note = str(raw.get("note") or "")
        remaining = qty

        while remaining > QTY_EPS and opens[sym]:
            lot = opens[sym][0]
            take = min(lot["qty"], remaining)
            buy_price = lot["price"]
            thesis = str(lot["note"] or "").strip()
            strategy = str(lot["strategy"] or "").strip()
            # tradermonty #714: missing price ≠ measured flat / −100%.
            if buy_price is None or sell_price is None:
                rounds.append(
                    {
                        "symbol": sym,
                        "quantity": take,
                        "buy_price": buy_price,
                        "sell_price": sell_price,
                        "buy_at": lot["timestamp"],
                        "sell_at": sell_ts,
                        "held": _hold_label(lot["timestamp"], sell_ts),
                        "thesis": thesis,
                        "strategy": strategy,
                        "score": lot.get("score"),
                        "confidence": lot.get("confidence"),
                        "source": lot.get("source") or "",
                        "exit_reason": UNOBSERVED_PRICE_REASON,
                        "exit_note": UNOBSERVED_PRICE_NOTE,
                        "profit_loss": None,
                        "profit_loss_pct": None,
                        "accounting": ACCOUNTING_SKIPPED,
                    }
                )
            else:
                cost = buy_price * take
                proceeds = sell_price * take
                pnl = proceeds - cost
                pnl_pct = (pnl / cost) * 100 if cost > QTY_EPS else None
                rounds.append(
                    {
                        "symbol": sym,
                        "quantity": take,
                        "buy_price": buy_price,
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
                        "profit_loss_pct": (
                            None if pnl_pct is None else round(pnl_pct, 2)
                        ),
                    }
                )

            lot["qty"] -= take
            remaining -= take
            if lot["qty"] <= QTY_EPS:
                opens[sym].popleft()

        # SELL left after FIFO — do not invent long P&L (legacy short /
        # corrupt ledger / oversell). Historical-only row; state unchanged.
        if remaining > QTY_EPS:
            rounds.append(
                {
                    "symbol": sym,
                    "quantity": remaining,
                    "buy_price": None,
                    "sell_price": sell_price,
                    "buy_at": "",
                    "sell_at": sell_ts,
                    "held": "",
                    "thesis": "",
                    "strategy": "",
                    "score": None,
                    "confidence": None,
                    "source": "",
                    "exit_reason": UNMATCHED_SELL_REASON,
                    "exit_note": UNMATCHED_SELL_NOTE,
                    "profit_loss": None,
                    "profit_loss_pct": None,
                    "accounting": ACCOUNTING_SKIPPED,
                }
            )

    rounds.reverse()
    if limit > 0:
        return rounds[:limit]
    return rounds


def is_unobserved_postmortem(row: Mapping[str, Any] | None) -> bool:
    """True when a closed-round skipped accounting for missing prices."""
    if not isinstance(row, Mapping):
        return False
    return (
        str(row.get("exit_reason") or "").strip().casefold()
        == UNOBSERVED_PRICE_REASON
    )


def is_unmatched_postmortem(row: Mapping[str, Any] | None) -> bool:
    """True when a closed-round row skipped accounting (orphan or unobserved)."""
    if not isinstance(row, Mapping):
        return False
    if str(row.get("accounting") or "").strip().casefold() == ACCOUNTING_SKIPPED:
        return True
    reason = str(row.get("exit_reason") or "").strip().casefold()
    return reason in {UNMATCHED_SELL_REASON, UNOBSERVED_PRICE_REASON}
