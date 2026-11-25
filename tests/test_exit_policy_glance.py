"""Stock exit-policy glance (display only)."""

from __future__ import annotations

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import (
    EXIT_POLICY_LINE_CHARS,
    _clip_exit_policy_line,
    _coerce_exit_policy_line_chars,
    build_exit_policy_glance,
)


def test_exit_policy_glance_stock_bands() -> None:
    g = build_exit_policy_glance()
    assert g["ready"] is True
    assert g["tone"] == "stock"
    assert g["take_profit_pct"] == 8.0
    assert g["stop_loss_pct"] == 5.0
    assert g["rotate_min_pct"] == 5.0
    assert g["designed_rr"] == 1.6
    assert "TP +8%" in g["line"]
    assert "SL −5%" in g["line"] or "SL -5%" in g["line"]
    assert "designed RR 1.6" in g["line"]
    assert "rotate ≥+5%" in g["line"] or "rotate >=+5%" in g["line"]


def test_coerce_exit_policy_line_chars_refuses_bool() -> None:
    """True→1 must not invent a one-char Exits strip; False must not wipe."""
    assert _coerce_exit_policy_line_chars(True) == EXIT_POLICY_LINE_CHARS
    assert _coerce_exit_policy_line_chars(False) == EXIT_POLICY_LINE_CHARS
    assert _coerce_exit_policy_line_chars(0) == EXIT_POLICY_LINE_CHARS
    assert _coerce_exit_policy_line_chars(None) == EXIT_POLICY_LINE_CHARS
    assert _coerce_exit_policy_line_chars(40) == 40


def test_clip_exit_policy_line_refuses_bool_ceiling() -> None:
    """True→1 must not invent line[:True]; False must not wipe via [:False]."""
    long = "x" * 120
    assert len(long) > EXIT_POLICY_LINE_CHARS
    default = _clip_exit_policy_line(long)
    assert len(default) == EXIT_POLICY_LINE_CHARS
    assert default.endswith("…")
    assert default == long[: EXIT_POLICY_LINE_CHARS - 1] + "…"
    assert _clip_exit_policy_line(long, True) == default
    assert _clip_exit_policy_line(long, False) == default
    assert _clip_exit_policy_line(long, 0) == default
    thin = _clip_exit_policy_line(long, 12)
    assert thin == long[:11] + "…"
    assert len(thin) == 12


def test_exit_policy_glance_refuses_bool_line_ceiling() -> None:
    """line_n=True must not invent a one-char strip; False must not wipe."""
    g = build_exit_policy_glance()
    g_bool = build_exit_policy_glance(line_n=True)
    g_false = build_exit_policy_glance(line_n=False)
    assert g_bool["line"] == g["line"]
    assert g_false["line"] == g["line"]
    assert len(g["line"]) <= EXIT_POLICY_LINE_CHARS
    g_short = build_exit_policy_glance(line_n=12)
    assert len(g_short["line"]) == 12
    assert g_short["line"].endswith("…")


def test_exit_policy_glance_in_chart_payload(tmp_path) -> None:
    payload = load_chart_payload(tmp_path)
    g = payload["exit_policy_glance"]
    assert g["ready"] is True
    assert "TP +8%" in g["line"]
    assert "designed RR 1.6" in g["line"]
