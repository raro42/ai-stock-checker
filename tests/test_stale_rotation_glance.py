"""Stale-name rotation honesty glance (display only)."""

from __future__ import annotations

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import (
    STALE_ROTATION_LINE_CHARS,
    _clip_stale_rotation_line,
    _coerce_stale_rotation_line_chars,
    build_stale_rotation_glance,
    load_desk_snapshot,
)
from stock_checker.exit_policy import DEFAULT_ROTATE_MIN_PROFIT_PCT


def test_coerce_stale_rotation_line_chars_refuses_bool() -> None:
    """True→1 must not invent a one-char Stale strip; False must not wipe."""
    assert _coerce_stale_rotation_line_chars(True) == STALE_ROTATION_LINE_CHARS
    assert _coerce_stale_rotation_line_chars(False) == STALE_ROTATION_LINE_CHARS
    assert _coerce_stale_rotation_line_chars(0) == STALE_ROTATION_LINE_CHARS
    assert _coerce_stale_rotation_line_chars(None) == STALE_ROTATION_LINE_CHARS
    assert _coerce_stale_rotation_line_chars(40) == 40


def test_clip_stale_rotation_line_refuses_bool_ceiling() -> None:
    """True→1 must not invent line[:True]; False must not wipe via [:False]."""
    long = "x" * 120
    assert len(long) > STALE_ROTATION_LINE_CHARS
    default = _clip_stale_rotation_line(long)
    assert len(default) == STALE_ROTATION_LINE_CHARS
    assert default.endswith("…")
    assert default == long[: STALE_ROTATION_LINE_CHARS - 1] + "…"
    assert _clip_stale_rotation_line(long, True) == default
    assert _clip_stale_rotation_line(long, False) == default
    assert _clip_stale_rotation_line(long, 0) == default
    thin = _clip_stale_rotation_line(long, 12)
    assert thin == long[:11] + "…"
    assert len(thin) == 12


def test_stale_rotation_glance_refuses_bool_line_ceiling() -> None:
    """line_n=True must not invent a one-char strip; False must not wipe."""
    g = build_stale_rotation_glance()
    g_bool = build_stale_rotation_glance(line_n=True)
    g_false = build_stale_rotation_glance(line_n=False)
    assert g_bool["line"] == g["line"]
    assert g_false["line"] == g["line"]
    assert len(g["line"]) <= STALE_ROTATION_LINE_CHARS
    g_short = build_stale_rotation_glance(line_n=12)
    assert len(g_short["line"]) == 12
    assert g_short["line"].endswith("…")


def test_stale_rotation_glance_line() -> None:
    g = build_stale_rotation_glance()
    assert g["ready"] is True
    assert g["tone"] == "stale"
    assert g["require_off_scan_list"] is True
    assert g["require_replacement"] is True
    assert g["winners_only"] is True
    assert g["rotate_min_pct"] == float(DEFAULT_ROTATE_MIN_PROFIT_PCT)
    assert "off full scan list" in g["line"]
    assert "top-N replacement" in g["line"]
    assert f"winners ≥+{float(DEFAULT_ROTATE_MIN_PROFIT_PCT):g}%" in g["line"]


def test_stale_rotation_glance_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["stale_rotation_glance"]
    assert g["ready"] is True
    assert g["tone"] == "stale"
    assert "off full scan list" in g["line"]
    assert "replacement" in g["line"]


def test_stale_rotation_glance_in_chart_payload(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    g = load_chart_payload(tmp_path)["stale_rotation_glance"]
    assert g["ready"] is True
    assert g["tone"] == "stale"
    assert "off full scan list" in g["line"]
    assert "top-N replacement" in g["line"]
