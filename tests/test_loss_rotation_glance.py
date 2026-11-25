"""No-loss-rotation policy glance (display only)."""

from __future__ import annotations

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import (
    LOSS_ROTATION_LINE_CHARS,
    _clip_loss_rotation_line,
    _coerce_loss_rotation_line_chars,
    build_loss_rotation_glance,
    load_desk_snapshot,
)
from stock_checker.exit_policy import DEFAULT_ROTATE_MIN_PROFIT_PCT


def test_coerce_loss_rotation_line_chars_refuses_bool() -> None:
    """True→1 must not invent a one-char Protect strip; False must not wipe."""
    assert _coerce_loss_rotation_line_chars(True) == LOSS_ROTATION_LINE_CHARS
    assert _coerce_loss_rotation_line_chars(False) == LOSS_ROTATION_LINE_CHARS
    assert _coerce_loss_rotation_line_chars(0) == LOSS_ROTATION_LINE_CHARS
    assert _coerce_loss_rotation_line_chars(None) == LOSS_ROTATION_LINE_CHARS
    assert _coerce_loss_rotation_line_chars(40) == 40


def test_clip_loss_rotation_line_refuses_bool_ceiling() -> None:
    """True→1 must not invent line[:True]; False must not wipe via [:False]."""
    long = "x" * 120
    assert len(long) > LOSS_ROTATION_LINE_CHARS
    default = _clip_loss_rotation_line(long)
    assert len(default) == LOSS_ROTATION_LINE_CHARS
    assert default.endswith("…")
    assert default == long[: LOSS_ROTATION_LINE_CHARS - 1] + "…"
    assert _clip_loss_rotation_line(long, True) == default
    assert _clip_loss_rotation_line(long, False) == default
    assert _clip_loss_rotation_line(long, 0) == default
    thin = _clip_loss_rotation_line(long, 12)
    assert thin == long[:11] + "…"
    assert len(thin) == 12


def test_loss_rotation_glance_refuses_bool_line_ceiling() -> None:
    """line_n=True must not invent a one-char strip; False must not wipe."""
    g = build_loss_rotation_glance()
    g_bool = build_loss_rotation_glance(line_n=True)
    g_false = build_loss_rotation_glance(line_n=False)
    assert g_bool["line"] == g["line"]
    assert g_false["line"] == g["line"]
    assert len(g["line"]) <= LOSS_ROTATION_LINE_CHARS
    g_short = build_loss_rotation_glance(line_n=12)
    assert len(g_short["line"]) == 12
    assert g_short["line"].endswith("…")


def test_loss_rotation_glance_ready() -> None:
    g = build_loss_rotation_glance()
    assert g["ready"] is True
    assert g["tone"] == "protect"
    assert g["loss_rotation"] is False
    assert g["rotate_min_pct"] == float(DEFAULT_ROTATE_MIN_PROFIT_PCT)
    assert "no loss-rotation" in g["line"]
    assert "winners" in g["line"]
    assert "overweight" in g["line"]


def test_loss_rotation_glance_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["loss_rotation_glance"]
    assert g["ready"] is True
    assert "no loss-rotation" in g["line"]


def test_loss_rotation_glance_in_chart_payload(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    g = load_chart_payload(tmp_path)["loss_rotation_glance"]
    assert g["ready"] is True
    assert g["tone"] == "protect"
    assert "no loss-rotation" in g["line"]
