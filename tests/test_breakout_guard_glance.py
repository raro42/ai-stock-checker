"""Stock breakout entry-guard glance (display only)."""

from __future__ import annotations

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import (
    BREAKOUT_GUARD_LINE_CHARS,
    _clip_breakout_guard_line,
    _coerce_breakout_guard_line_chars,
    build_breakout_guard_glance,
    load_desk_snapshot,
)
from stock_checker.entry_guards import BREAKOUT_PCT_MAX, BREAKOUT_PCT_MIN


def test_coerce_breakout_guard_line_chars_refuses_bool() -> None:
    """True→1 must not invent a one-char Breakouts strip; False must not wipe."""
    assert _coerce_breakout_guard_line_chars(True) == BREAKOUT_GUARD_LINE_CHARS
    assert _coerce_breakout_guard_line_chars(False) == BREAKOUT_GUARD_LINE_CHARS
    assert _coerce_breakout_guard_line_chars(0) == BREAKOUT_GUARD_LINE_CHARS
    assert _coerce_breakout_guard_line_chars(None) == BREAKOUT_GUARD_LINE_CHARS
    assert _coerce_breakout_guard_line_chars(40) == 40


def test_clip_breakout_guard_line_refuses_bool_ceiling() -> None:
    """True→1 must not invent line[:True]; False must not wipe via [:False]."""
    long = "x" * 120
    assert len(long) > BREAKOUT_GUARD_LINE_CHARS
    default = _clip_breakout_guard_line(long)
    assert len(default) == BREAKOUT_GUARD_LINE_CHARS
    assert default.endswith("…")
    assert default == long[: BREAKOUT_GUARD_LINE_CHARS - 1] + "…"
    assert _clip_breakout_guard_line(long, True) == default
    assert _clip_breakout_guard_line(long, False) == default
    assert _clip_breakout_guard_line(long, 0) == default
    thin = _clip_breakout_guard_line(long, 12)
    assert thin == long[:11] + "…"
    assert len(thin) == 12


def test_breakout_guard_glance_refuses_bool_line_ceiling() -> None:
    """line_n=True must not invent a one-char strip; False must not wipe."""
    g = build_breakout_guard_glance()
    g_bool = build_breakout_guard_glance(line_n=True)
    g_false = build_breakout_guard_glance(line_n=False)
    assert g_bool["line"] == g["line"]
    assert g_false["line"] == g["line"]
    assert len(g["line"]) <= BREAKOUT_GUARD_LINE_CHARS
    g_short = build_breakout_guard_glance(line_n=12)
    assert len(g_short["line"]) == 12
    assert g_short["line"].endswith("…")


def test_breakout_guard_glance_ready() -> None:
    g = build_breakout_guard_glance()
    assert g["ready"] is True
    assert g["tone"] == "breakout"
    assert g["pullback_min_pct"] == float(BREAKOUT_PCT_MIN)
    assert g["pullback_max_pct"] == float(BREAKOUT_PCT_MAX)
    assert "AI BUY" in g["line"]
    assert "LOW blocked" in g["line"]
    assert "pullback" in g["line"]


def test_breakout_guard_glance_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["breakout_guard_glance"]
    assert g["ready"] is True
    assert "breakouts" in g["line"]


def test_breakout_guard_glance_in_chart_payload(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    g = load_chart_payload(tmp_path)["breakout_guard_glance"]
    assert g["ready"] is True
    assert g["tone"] == "breakout"
    assert "AI BUY" in g["line"]
