"""Build short ledger notes for paper fills (desk Book)."""

from __future__ import annotations

from typing import Any, Mapping

from stock_checker.technical_indicators import _finite_signed, coerce_score

NOTE_MAX = 160


def _clip(text: str, limit: int = NOTE_MAX) -> str:
    clean = " ".join(str(text).split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rstrip() + "…"


def buy_note_from_opportunity(
    opp: Mapping[str, Any] | None,
    *,
    source: str,
    recommendation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    One-line buy context from a scan row and optional recommender output.

    Stored on BUY rows in trades.jsonl for Book / audit — not full AI dumps.
    """
    row = opp or {}
    rec = recommendation or {}

    note = ""
    reasons = rec.get("reasons") or row.get("reasons")
    if isinstance(reasons, list) and reasons:
        note = str(reasons[0])
    elif row.get("ai_reasoning"):
        note = str(row["ai_reasoning"])
    elif row.get("reasoning"):
        note = str(row["reasoning"])

    strategy = str(row.get("strategy") or rec.get("strategy") or "").strip()
    confidence = rec.get("confidence") or row.get("ai_confidence") or row.get("confidence")

    # tradermonty #700/#655 + xang1234/portfolio AI: never float(True)→1.0 score.
    score_raw = coerce_score(rec.get("score", row.get("score")))
    score = round(score_raw, 1) if score_raw is not None else None

    ctx: dict[str, Any] = {"source": str(source)[:24]}
    if strategy:
        ctx["strategy"] = strategy[:32]
    if note.strip():
        ctx["note"] = _clip(note)
    if score is not None:
        ctx["score"] = score
    if confidence:
        ctx["confidence"] = str(confidence)[:16]
    return ctx


def sell_note_from_exit(
    *,
    exit_reason: str,
    profit_pct: float | None = None,
    threshold: float | None = None,
    detail: str = "",
) -> dict[str, Any]:
    """Short ledger note for SELL rows (Book / audit)."""
    reason = str(exit_reason or "exit")[:24]
    # Refuse bool/gap so True→+1.0% cannot invent TP/SL note copy.
    pct = float(profit_pct) if _finite_signed(profit_pct) else None  # type: ignore[arg-type]
    thr = float(threshold) if _finite_signed(threshold) else None  # type: ignore[arg-type]
    note = ""
    if reason == "tp" and pct is not None and thr is not None:
        note = f"Profit target {pct:+.1f}% (thr +{thr:g}%)"
    elif reason == "sl" and pct is not None and thr is not None:
        note = f"Stop loss {pct:+.1f}% (thr −{thr:g}%)"
    elif reason == "rotation":
        note = detail or "Scan rotation (winner past hurdle)"
    elif reason == "trim":
        note = detail or "Overweight trim"
    elif reason == "stale":
        note = detail or "Stale winner exit"
    elif detail:
        note = detail
    else:
        note = reason.replace("_", " ")

    ctx: dict[str, Any] = {"exit_reason": reason, "source": "exit_policy"}
    if note.strip():
        ctx["note"] = _clip(note)
    return ctx
