"""Build short ledger notes for paper fills (desk Book)."""

from __future__ import annotations

from typing import Any, Mapping

from stock_checker.technical_indicators import (
    _finite_signed,
    coerce_nonneg_int,
    coerce_score,
)

NOTE_MAX = 160
SOURCE_MAX = 24
STRATEGY_MAX = 32
CONFIDENCE_MAX = 16
EXIT_REASON_MAX = 24


def _coerce_note_clip_chars(
    value: object, default: int = NOTE_MAX
) -> int:
    """Positive Book fill-note char ceiling, or ``default`` when bool/gap/≤0.

    tradermonty #700/#655 + xang1234/portfolio AI: ``True→1`` must not invent
    a one-char ledger note (``T…``); ``False→0`` must not wipe via
    ``s[:-1]`` (LAYA/AI-validate reason clip peer — score/% refuse already
    covered; note ceilings were still open).
    """
    n = coerce_nonneg_int(value)
    if n is None or n <= 0:
        return int(default)
    return n


def _coerce_field_clip_chars(
    value: object, default: int
) -> int:
    """Positive Book fill-tag char ceiling, or ``default`` when bool/gap/≤0.

    FinRobot + tradermonty #700/#655 + xang1234/portfolio AI: ``True→1`` must
    not invent a one-char source/strategy/confidence/exit tag via ``s[:True]``;
    ``False→0`` must not wipe (note clip peer — score/% refuse already covered;
    field ceilings were still bare ``[:24]``/``[:32]``/``[:16]``).
    """
    n = coerce_nonneg_int(value)
    if n is None or n <= 0:
        return int(default)
    return n


def _clip(text: object, limit: object = NOTE_MAX) -> str:
    ceiling = _coerce_note_clip_chars(limit)
    clean = " ".join(str(text or "").split())
    if len(clean) <= ceiling:
        return clean
    return clean[: ceiling - 1].rstrip() + "…"


def _clip_field(
    text: object,
    limit: object,
    *,
    default: int,
) -> str:
    """Hard-cut ledger tag (source/strategy/confidence/exit_reason)."""
    ceiling = _coerce_field_clip_chars(limit, default)
    return str(text or "")[:ceiling]


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

    ctx: dict[str, Any] = {
        "source": _clip_field(source, SOURCE_MAX, default=SOURCE_MAX),
    }
    if strategy:
        ctx["strategy"] = _clip_field(
            strategy, STRATEGY_MAX, default=STRATEGY_MAX
        )
    if note.strip():
        ctx["note"] = _clip(note)
    if score is not None:
        ctx["score"] = score
    if confidence:
        ctx["confidence"] = _clip_field(
            confidence, CONFIDENCE_MAX, default=CONFIDENCE_MAX
        )
    return ctx


def sell_note_from_exit(
    *,
    exit_reason: str,
    profit_pct: float | None = None,
    threshold: float | None = None,
    detail: str = "",
) -> dict[str, Any]:
    """Short ledger note for SELL rows (Book / audit)."""
    reason = _clip_field(
        exit_reason or "exit", EXIT_REASON_MAX, default=EXIT_REASON_MAX
    )
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
