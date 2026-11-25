"""Book risk glance (display only)."""

from __future__ import annotations

from openbb_backend.desk import (
    BOOK_RISK_LINE_CHARS,
    _clip_book_risk_line,
    _coerce_book_risk_line_chars,
    build_book_risk_glance,
)


def test_book_risk_glance_empty() -> None:
    assert build_book_risk_glance(None)["ready"] is False
    assert build_book_risk_glance({})["ready"] is False
    assert build_book_risk_glance({"posture": "open"})["ready"] is False


def test_book_risk_glance_open() -> None:
    g = build_book_risk_glance(
        {
            "slots": "2/5",
            "posture": "open",
            "note": "2/5 slots · open · cash 40%",
            "concentration_warn": False,
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "open"
    assert g["posture"] == "open"
    assert g["slots"] == "2/5"
    assert "2/5 slots" in g["line"]
    assert g["concentration_warn"] is False


def test_book_risk_glance_overweight() -> None:
    g = build_book_risk_glance(
        {
            "slots": "6/5",
            "posture": "overweight",
            "note": "6/5 slots · overweight · largest AAPL 35%",
            "concentration_warn": True,
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "overweight"
    assert g["posture"] == "overweight"
    assert g["concentration_warn"] is True


def test_coerce_book_risk_line_chars_refuses_bool() -> None:
    """True→1 must not invent a one-char risk strip; False must not wipe."""
    assert _coerce_book_risk_line_chars(True) == BOOK_RISK_LINE_CHARS
    assert _coerce_book_risk_line_chars(False) == BOOK_RISK_LINE_CHARS
    assert _coerce_book_risk_line_chars(0) == BOOK_RISK_LINE_CHARS
    assert _coerce_book_risk_line_chars(None) == BOOK_RISK_LINE_CHARS
    assert _coerce_book_risk_line_chars(40) == 40


def test_clip_book_risk_line_refuses_bool_ceiling() -> None:
    """True→1 must not invent line[:True]; False must not wipe via [:False]."""
    long = "x" * 120
    assert len(long) > BOOK_RISK_LINE_CHARS
    default = _clip_book_risk_line(long)
    assert len(default) == BOOK_RISK_LINE_CHARS
    assert default.endswith("…")
    assert default == long[: BOOK_RISK_LINE_CHARS - 1] + "…"
    assert _clip_book_risk_line(long, True) == default
    assert _clip_book_risk_line(long, False) == default
    assert _clip_book_risk_line(long, 0) == default
    thin = _clip_book_risk_line(long, 12)
    assert thin == long[:11] + "…"
    assert len(thin) == 12
    assert _clip_book_risk_line("short") == "short"
    assert _clip_book_risk_line("") == ""
    assert _clip_book_risk_line(None) == ""


def test_book_risk_glance_truncates_note() -> None:
    long = "x" * 120
    g = build_book_risk_glance(
        {"slots": "1/5", "posture": "at_cap", "note": long}
    )
    assert g["ready"] is True
    assert g["tone"] == "at_cap"
    assert g["line"].endswith("…")
    assert len(g["line"]) <= BOOK_RISK_LINE_CHARS
    clipped = long[: BOOK_RISK_LINE_CHARS - 1] + "…"
    assert g["line"] == clipped


def test_book_risk_glance_refuses_bool_line_ceiling() -> None:
    """True→1 must not invent a one-char at_cap strip via line[:True]."""
    long = "x" * 120
    clipped = long[: BOOK_RISK_LINE_CHARS - 1] + "…"
    risk = {"slots": "1/5", "posture": "at_cap", "note": long}
    g_true = build_book_risk_glance(risk, line_n=True)
    assert g_true["line"] == clipped
    g_false = build_book_risk_glance(risk, line_n=False)
    assert g_false["line"] == clipped
    g_short = build_book_risk_glance(risk, line_n=8)
    assert g_short["line"] == long[:7] + "…"
    assert g_short["line"].endswith("…")
    assert len(g_short["line"]) == 8
