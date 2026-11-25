"""FinRobot multi-role research contract glance (display only)."""

from __future__ import annotations

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import (
    AI_ROLES_LINE_CHARS,
    _clip_ai_roles_line,
    _coerce_ai_roles_line_chars,
    build_ai_roles_glance,
    load_desk_snapshot,
)


def test_coerce_ai_roles_line_chars_refuses_bool() -> None:
    """True→1 must not invent a one-char AI-roles strip; False must not wipe."""
    assert _coerce_ai_roles_line_chars(True) == AI_ROLES_LINE_CHARS
    assert _coerce_ai_roles_line_chars(False) == AI_ROLES_LINE_CHARS
    assert _coerce_ai_roles_line_chars(0) == AI_ROLES_LINE_CHARS
    assert _coerce_ai_roles_line_chars(None) == AI_ROLES_LINE_CHARS
    assert _coerce_ai_roles_line_chars(40) == 40


def test_clip_ai_roles_line_refuses_bool_ceiling() -> None:
    """True→1 must not invent line[:True]; False must not wipe via [:False]."""
    long = "x" * 120
    assert len(long) > AI_ROLES_LINE_CHARS
    default = _clip_ai_roles_line(long)
    assert len(default) == AI_ROLES_LINE_CHARS
    assert default.endswith("…")
    assert default == long[: AI_ROLES_LINE_CHARS - 1] + "…"
    assert _clip_ai_roles_line(long, True) == default
    assert _clip_ai_roles_line(long, False) == default
    assert _clip_ai_roles_line(long, 0) == default
    thin = _clip_ai_roles_line(long, 12)
    assert thin == long[:11] + "…"
    assert len(thin) == 12


def test_ai_roles_glance_refuses_bool_line_ceiling() -> None:
    """line_n=True must not invent a one-char strip; False must not wipe."""
    g = build_ai_roles_glance()
    g_bool = build_ai_roles_glance(line_n=True)
    g_false = build_ai_roles_glance(line_n=False)
    assert g_bool["line"] == g["line"]
    assert g_false["line"] == g["line"]
    assert len(g["line"]) <= AI_ROLES_LINE_CHARS
    g_short = build_ai_roles_glance(line_n=12)
    assert len(g_short["line"]) == 12
    assert g_short["line"].endswith("…")


def test_ai_roles_glance_line() -> None:
    g = build_ai_roles_glance()
    assert g["ready"] is True
    assert g["tone"] == "roles"
    assert g["roles"] == ("bull", "bear", "risk")
    assert g["disagree_forces_hold"] is True
    assert g["risk_veto_forces_hold"] is True
    assert "bull" in g["line"]
    assert "bear" in g["line"]
    assert "risk" in g["line"]
    assert "disagree→HOLD" in g["line"]
    assert "risk.ok=false→HOLD" in g["line"]


def test_ai_roles_glance_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["ai_roles_glance"]
    assert g["ready"] is True
    assert g["tone"] == "roles"
    assert "bull" in g["line"]
    assert "HOLD" in g["line"]


def test_ai_roles_glance_in_chart_payload(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    g = load_chart_payload(tmp_path)["ai_roles_glance"]
    assert g["ready"] is True
    assert g["tone"] == "roles"
    assert "disagree→HOLD" in g["line"]
    assert "risk.ok=false→HOLD" in g["line"]
