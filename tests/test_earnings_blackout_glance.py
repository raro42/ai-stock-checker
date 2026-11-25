"""Stock earnings blackout policy glance (display only)."""

from __future__ import annotations

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import (
    EARNINGS_BLACKOUT_LINE_CHARS,
    _clip_earnings_blackout_line,
    _coerce_earnings_blackout_line_chars,
    build_earnings_blackout_glance,
    load_desk_snapshot,
)


def test_earnings_blackout_glance_window() -> None:
    g = build_earnings_blackout_glance()
    assert g["ready"] is True
    assert g["tone"] == "stock"
    assert g["days_before"] == 2.0
    assert g["days_after"] == 1.0
    assert g["fail_open"] is True
    assert g["missing_calendar"] == "allow"
    assert g["empty_window"] == "allow_suspect"
    assert g["malformed"] == "allow_suspect"
    assert "2d/1d" in g["line"]
    assert "NY date" in g["line"]
    assert g["clock"] == "America/New_York"
    assert "empty/bad Yahoo → allow (suspect)" in g["line"]
    assert "crypto exempt" in g["line"]


def test_coerce_earnings_blackout_line_chars_refuses_bool() -> None:
    """True→1 must not invent a one-char Earnings strip; False must not wipe."""
    assert _coerce_earnings_blackout_line_chars(True) == EARNINGS_BLACKOUT_LINE_CHARS
    assert _coerce_earnings_blackout_line_chars(False) == EARNINGS_BLACKOUT_LINE_CHARS
    assert _coerce_earnings_blackout_line_chars(0) == EARNINGS_BLACKOUT_LINE_CHARS
    assert _coerce_earnings_blackout_line_chars(None) == EARNINGS_BLACKOUT_LINE_CHARS
    assert _coerce_earnings_blackout_line_chars(40) == 40


def test_clip_earnings_blackout_line_refuses_bool_ceiling() -> None:
    """True→1 must not invent line[:True]; False must not wipe via [:False]."""
    long = "x" * 120
    assert len(long) > EARNINGS_BLACKOUT_LINE_CHARS
    default = _clip_earnings_blackout_line(long)
    assert len(default) == EARNINGS_BLACKOUT_LINE_CHARS
    assert default.endswith("…")
    assert default == long[: EARNINGS_BLACKOUT_LINE_CHARS - 1] + "…"
    assert _clip_earnings_blackout_line(long, True) == default
    assert _clip_earnings_blackout_line(long, False) == default
    assert _clip_earnings_blackout_line(long, 0) == default
    thin = _clip_earnings_blackout_line(long, 12)
    assert thin == long[:11] + "…"
    assert len(thin) == 12


def test_earnings_blackout_glance_refuses_bool_line_ceiling() -> None:
    """line_n=True must not invent a one-char strip; False must not wipe."""
    g = build_earnings_blackout_glance()
    g_bool = build_earnings_blackout_glance(line_n=True)
    g_false = build_earnings_blackout_glance(line_n=False)
    assert g_bool["line"] == g["line"]
    assert g_false["line"] == g["line"]
    assert len(g["line"]) <= EARNINGS_BLACKOUT_LINE_CHARS
    g_short = build_earnings_blackout_glance(line_n=12)
    assert len(g_short["line"]) == 12
    assert g_short["line"].endswith("…")


def test_earnings_blackout_glance_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["earnings_blackout_glance"]
    assert g["ready"] is True
    assert "NY date" in g["line"]
    assert g["clock"] == "America/New_York"
    assert "empty/bad Yahoo → allow (suspect)" in g["line"]
    assert g["fail_open"] is True
    assert g["empty_window"] == "allow_suspect"
    assert g["malformed"] == "allow_suspect"


def test_earnings_blackout_glance_in_chart_payload(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    g = load_chart_payload(tmp_path)["earnings_blackout_glance"]
    assert g["ready"] is True
    assert "2d/1d" in g["line"]
    assert "NY date" in g["line"]
    assert g["clock"] == "America/New_York"
    assert "empty/bad Yahoo → allow (suspect)" in g["line"]
    assert "crypto exempt" in g["line"]
