"""AI validate memory retention / Ideas limit must refuse bool invents."""

from __future__ import annotations

from pathlib import Path

from stock_checker.ai_validate_memory import (
    IDEAS_LIMIT,
    VALIDATE_MEMORY_CAP,
    _DEFAULT_CLIP_CHARS,
    _DEFAULT_REASON_LINES,
    _clip,
    _clip_reasons,
    _coerce_clip_chars,
    _coerce_clip_reason_lines,
    _coerce_recent_debates_limit,
    _coerce_validate_memory_cap,
    load_ai_validate_memory,
    recent_ai_debates,
    record_ai_validate,
)


def test_coerce_validate_memory_cap_refuses_bool() -> None:
    """True→1 must not invent a one-row FinRobot debate ring."""
    assert _coerce_validate_memory_cap(True) == VALIDATE_MEMORY_CAP
    assert _coerce_validate_memory_cap(False) == VALIDATE_MEMORY_CAP
    assert _coerce_validate_memory_cap(5) == 5
    assert _coerce_validate_memory_cap(0) == 0


def test_coerce_recent_debates_limit_refuses_bool() -> None:
    """True→1 must not invent a one-row Ideas transcript; False must not wipe."""
    assert _coerce_recent_debates_limit(True) == IDEAS_LIMIT
    assert _coerce_recent_debates_limit(False) == IDEAS_LIMIT
    assert _coerce_recent_debates_limit(3) == 3
    assert _coerce_recent_debates_limit(0) == 0


def test_record_ai_validate_refuses_bool_cap(tmp_path: Path) -> None:
    """True→1 must not shrink the debate ring to a single row."""
    for i in range(5):
        record_ai_validate(
            tmp_path,
            {"action": "HOLD", "confidence": "LOW", "score": 0, "reasons": ["x"]},
            symbol=f"T{i}",
            cap=True,
        )
    # Without refuse, int(True)→1 would keep only the newest event.
    assert len(load_ai_validate_memory(tmp_path)) == 5

    for i in range(3):
        record_ai_validate(
            tmp_path,
            {"action": "HOLD", "confidence": "LOW", "score": 0, "reasons": ["y"]},
            symbol=f"F{i}",
            cap=False,
        )
    # False→0 via int() then max(1,0)→1 would also invent a 1-row ring.
    assert len(load_ai_validate_memory(tmp_path)) == 8

    for i, letter in enumerate("abc"):
        record_ai_validate(
            tmp_path,
            {"action": "HOLD", "confidence": "LOW", "score": 0, "reasons": ["z"]},
            symbol=letter,
            cap=2,
        )
    assert len(load_ai_validate_memory(tmp_path)) == 2


def test_recent_ai_debates_refuses_bool_limit(tmp_path: Path) -> None:
    """Bool Ideas limit falls back to IDEAS_LIMIT (not True→1 / False→0)."""
    for i in range(5):
        record_ai_validate(
            tmp_path,
            {"action": "HOLD", "confidence": "LOW", "score": 0, "reasons": ["x"]},
            symbol=f"R{i}",
            cap=10,
        )
    assert len(recent_ai_debates(tmp_path, limit=True)) == 5
    assert len(recent_ai_debates(tmp_path, limit=False)) == 5
    assert len(recent_ai_debates(tmp_path, limit=2)) == 2


def test_coerce_clip_chars_refuses_bool() -> None:
    """True→1 must not invent a one-char Ideas note; False must not wipe."""
    assert _coerce_clip_chars(True) == _DEFAULT_CLIP_CHARS
    assert _coerce_clip_chars(False) == _DEFAULT_CLIP_CHARS
    assert _coerce_clip_chars(0) == _DEFAULT_CLIP_CHARS
    assert _coerce_clip_chars(None) == _DEFAULT_CLIP_CHARS
    assert _coerce_clip_chars(40) == 40


def test_coerce_clip_reason_lines_refuses_bool() -> None:
    """True→1 must not invent a one-line reason strip; False must not wipe."""
    assert _coerce_clip_reason_lines(True) == _DEFAULT_REASON_LINES
    assert _coerce_clip_reason_lines(False) == _DEFAULT_REASON_LINES
    assert _coerce_clip_reason_lines(None) == _DEFAULT_REASON_LINES
    assert _coerce_clip_reason_lines(0) == 0
    assert _coerce_clip_reason_lines(3) == 3


def test_clip_refuses_bool_char_ceiling() -> None:
    """True→1 must not invent ``T…``; False must not wipe via s[:-1]."""
    note = "trend still intact near highs"
    assert _clip(note, True) == note
    assert _clip(note, False) == note
    assert _clip(note, 0) == note
    assert _clip(note, 8) == "trend s…"


def test_clip_reasons_refuses_bool_ceilings() -> None:
    """True→1 line/char must not invent a tiny FinRobot reason strip."""
    reasons = [f"reason-{i}-still-intact" for i in range(5)]
    assert _clip_reasons(reasons, max_lines=True) == reasons
    assert _clip_reasons(reasons, max_lines=False) == reasons
    assert _clip_reasons(reasons, max_lines=2) == reasons[:2]
    # Char ceiling bool must not collapse each reason to ``r…``.
    clipped = _clip_reasons(reasons, max_lines=2, line_n=True)
    assert clipped == reasons[:2]
    assert all("…" not in row for row in clipped)
    assert _clip_reasons(reasons, max_lines=0) == []
