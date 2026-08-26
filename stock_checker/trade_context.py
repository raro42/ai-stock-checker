"""Build short ledger notes for paper fills (desk Book)."""

from __future__ import annotations

from typing import Any, Mapping

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

    score = None
    score_raw = rec.get("score", row.get("score"))
    if score_raw is not None:
        try:
            score = round(float(score_raw), 1)
        except (TypeError, ValueError):
            score = None

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
    note = ""
    if reason == "tp" and profit_pct is not None and threshold is not None:
        note = f"Profit target {profit_pct:+.1f}% (thr +{threshold:g}%)"
    elif reason == "sl" and profit_pct is not None and threshold is not None:
        note = f"Stop loss {profit_pct:+.1f}% (thr −{threshold:g}%)"
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
