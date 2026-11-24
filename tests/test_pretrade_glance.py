"""Pre-trade PASS/WARN/FAIL glance (display only)."""

from __future__ import annotations

from openbb_backend.desk import (
    PRETRADE_NOTES_CHARS,
    _clip_pretrade_notes,
    _coerce_pretrade_notes_chars,
    build_pretrade_glance,
)


def test_pretrade_glance_empty() -> None:
    assert build_pretrade_glance(None, None)["ready"] is False
    assert build_pretrade_glance("", [])["ready"] is False
    assert build_pretrade_glance("maybe", ["ok"])["ready"] is False


def test_pretrade_glance_pass() -> None:
    g = build_pretrade_glance("pass", ["ok"])
    assert g["ready"] is True
    assert g["level"] == "PASS"
    assert g["tone"] == "pass"
    assert g["line"] == "PASS · ok"
    assert g["notes"] == ["ok"]


def test_pretrade_glance_warn_joins_notes() -> None:
    g = build_pretrade_glance(
        "WARN",
        ["UTC day realized €-12.00", "fee burn high vs PnL"],
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert "WARN ·" in g["line"]
    assert "fee burn" in g["line"]


def test_coerce_pretrade_notes_chars_refuses_bool() -> None:
    """True→1 must not invent a one-char pretrade strip; False must not wipe."""
    assert _coerce_pretrade_notes_chars(True) == PRETRADE_NOTES_CHARS
    assert _coerce_pretrade_notes_chars(False) == PRETRADE_NOTES_CHARS
    assert _coerce_pretrade_notes_chars(0) == PRETRADE_NOTES_CHARS
    assert _coerce_pretrade_notes_chars(None) == PRETRADE_NOTES_CHARS
    assert _coerce_pretrade_notes_chars(40) == 40


def test_clip_pretrade_notes_refuses_bool_ceiling() -> None:
    """True→1 must not invent joined[:True]; False must not wipe via [:False]."""
    long = "x" * 120
    assert len(long) > PRETRADE_NOTES_CHARS
    default = _clip_pretrade_notes(long)
    assert len(default) == PRETRADE_NOTES_CHARS
    assert default.endswith("…")
    assert default == long[: PRETRADE_NOTES_CHARS - 1] + "…"
    assert _clip_pretrade_notes(long, True) == default
    assert _clip_pretrade_notes(long, False) == default
    assert _clip_pretrade_notes(long, 0) == default
    thin = _clip_pretrade_notes(long, 12)
    assert thin == long[:11] + "…"
    assert len(thin) == 12
    assert _clip_pretrade_notes("short") == "short"
    assert _clip_pretrade_notes("") == ""
    assert _clip_pretrade_notes(None) == ""


def test_pretrade_glance_fail_truncates() -> None:
    long = "x" * 120
    g = build_pretrade_glance("FAIL", [long])
    assert g["ready"] is True
    assert g["tone"] == "fail"
    assert g["line"].endswith("…")
    assert len(g["line"]) <= 110
    clipped = long[: PRETRADE_NOTES_CHARS - 1] + "…"
    assert g["line"] == f"FAIL · {clipped}"


def test_pretrade_glance_refuses_bool_notes_ceiling() -> None:
    """True→1 must not invent a one-char FAIL strip via joined[:True]."""
    long = "x" * 120
    clipped = long[: PRETRADE_NOTES_CHARS - 1] + "…"
    g_true = build_pretrade_glance("FAIL", [long], notes_n=True)
    assert g_true["line"] == f"FAIL · {clipped}"
    g_false = build_pretrade_glance("FAIL", [long], notes_n=False)
    assert g_false["line"] == f"FAIL · {clipped}"
    g_short = build_pretrade_glance("FAIL", [long], notes_n=8)
    assert g_short["line"] == f"FAIL · {long[:7]}…"
    assert g_short["line"].endswith("…")
    assert len(g_short["line"]) == len("FAIL · ") + 8
