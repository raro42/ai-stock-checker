"""Gate roles honesty glance (A14; display only)."""

from __future__ import annotations

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import (
    GATE_ROLES_LINE_CHARS,
    _clip_gate_roles_line,
    _coerce_gate_roles_line_chars,
    build_gate_roles_glance,
    load_desk_snapshot,
)


def test_coerce_gate_roles_line_chars_refuses_bool() -> None:
    """True→1 must not invent a one-char Roles strip; False must not wipe."""
    assert _coerce_gate_roles_line_chars(True) == GATE_ROLES_LINE_CHARS
    assert _coerce_gate_roles_line_chars(False) == GATE_ROLES_LINE_CHARS
    assert _coerce_gate_roles_line_chars(0) == GATE_ROLES_LINE_CHARS
    assert _coerce_gate_roles_line_chars(None) == GATE_ROLES_LINE_CHARS
    assert _coerce_gate_roles_line_chars(40) == 40


def test_clip_gate_roles_line_refuses_bool_ceiling() -> None:
    """True→1 must not invent line[:True]; False must not wipe via [:False]."""
    long = "x" * 120
    assert len(long) > GATE_ROLES_LINE_CHARS
    default = _clip_gate_roles_line(long)
    assert len(default) == GATE_ROLES_LINE_CHARS
    assert default.endswith("…")
    assert default == long[: GATE_ROLES_LINE_CHARS - 1] + "…"
    assert _clip_gate_roles_line(long, True) == default
    assert _clip_gate_roles_line(long, False) == default
    assert _clip_gate_roles_line(long, 0) == default
    thin = _clip_gate_roles_line(long, 12)
    assert thin == long[:11] + "…"
    assert len(thin) == 12


def test_gate_roles_glance_refuses_bool_line_ceiling() -> None:
    """line_n=True must not invent a one-char strip; False must not wipe."""
    runtime = {"regime_gate": True, "rs_gate": True, "breadth_gate": True}
    g = build_gate_roles_glance(runtime)
    g_bool = build_gate_roles_glance(runtime, line_n=True)
    g_false = build_gate_roles_glance(runtime, line_n=False)
    assert g_bool["line"] == g["line"]
    assert g_false["line"] == g["line"]
    assert len(g["line"]) <= GATE_ROLES_LINE_CHARS
    g_short = build_gate_roles_glance(runtime, line_n=12)
    assert len(g_short["line"]) == 12
    assert g_short["line"].endswith("…")


def test_gate_roles_glance_overlap() -> None:
    g = build_gate_roles_glance(
        {"regime_gate": True, "rs_gate": True, "breadth_gate": True}
    )
    assert g["ready"] is True
    assert g["tone"] == "overlap"
    assert g["overlap"] is True
    assert g["prefer_rs_off_if_starved"] is True
    assert "starve→RS off first" in g["line"]
    assert "abs vs rel" in g["line"]
    assert "benchmark trend" in g["regime_role"]
    assert "relative" in g["rs_role"]
    assert "scan-list" in g["breadth_role"]


def test_gate_roles_glance_no_overlap() -> None:
    g = build_gate_roles_glance(
        {"regime_gate": True, "rs_gate": False, "breadth_gate": True}
    )
    assert g["ready"] is True
    assert g["tone"] == "roles"
    assert g["overlap"] is False
    assert g["regime"] is True
    assert g["rs"] is False
    assert "RS off" in g["line"]
    assert "starve→RS off first" in g["line"]


def test_gate_roles_glance_empty_runtime() -> None:
    g = build_gate_roles_glance(None)
    assert g["ready"] is False
    assert g["line"] == ""


def test_gate_roles_glance_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["gate_roles_glance"]
    assert g["ready"] is True
    assert g["prefer_rs_off_if_starved"] is True
    assert "RS off first" in g["line"] or "starve→RS off first" in g["line"]


def test_gate_roles_glance_in_chart_payload(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    g = load_chart_payload(tmp_path)["gate_roles_glance"]
    assert g["ready"] is True
    assert g["prefer_rs_off_if_starved"] is True
    assert "starve→RS off first" in g["line"]
