"""Junk / noise filter policy glance (display only)."""

from __future__ import annotations

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import (
    JUNK_FILTER_LINE_CHARS,
    _clip_junk_filter_line,
    _coerce_junk_filter_line_chars,
    build_junk_filter_glance,
    load_desk_snapshot,
)
from stock_checker.exit_policy import DEFAULT_CRYPTO_ENTRY_MIN_USD


def test_coerce_junk_filter_line_chars_refuses_bool() -> None:
    """True→1 must not invent a one-char Filter strip; False must not wipe."""
    assert _coerce_junk_filter_line_chars(True) == JUNK_FILTER_LINE_CHARS
    assert _coerce_junk_filter_line_chars(False) == JUNK_FILTER_LINE_CHARS
    assert _coerce_junk_filter_line_chars(0) == JUNK_FILTER_LINE_CHARS
    assert _coerce_junk_filter_line_chars(None) == JUNK_FILTER_LINE_CHARS
    assert _coerce_junk_filter_line_chars(40) == 40


def test_clip_junk_filter_line_refuses_bool_ceiling() -> None:
    """True→1 must not invent line[:True]; False must not wipe via [:False]."""
    long = "x" * 120
    assert len(long) > JUNK_FILTER_LINE_CHARS
    default = _clip_junk_filter_line(long)
    assert len(default) == JUNK_FILTER_LINE_CHARS
    assert default.endswith("…")
    assert default == long[: JUNK_FILTER_LINE_CHARS - 1] + "…"
    assert _clip_junk_filter_line(long, True) == default
    assert _clip_junk_filter_line(long, False) == default
    assert _clip_junk_filter_line(long, 0) == default
    thin = _clip_junk_filter_line(long, 12)
    assert thin == long[:11] + "…"
    assert len(thin) == 12


def test_junk_filter_glance_refuses_bool_line_ceiling() -> None:
    """line_n=True must not invent a one-char strip; False must not wipe."""
    g = build_junk_filter_glance()
    g_bool = build_junk_filter_glance(line_n=True)
    g_false = build_junk_filter_glance(line_n=False)
    assert g_bool["line"] == g["line"]
    assert g_false["line"] == g["line"]
    assert len(g["line"]) <= JUNK_FILTER_LINE_CHARS
    g_short = build_junk_filter_glance(line_n=12)
    assert len(g_short["line"]) == 12
    assert g_short["line"].endswith("…")


def test_junk_filter_glance_ready() -> None:
    g = build_junk_filter_glance()
    assert g["ready"] is True
    assert g["tone"] == "filter"
    assert g["stables_blocked"] is True
    assert g["leveraged_blocked"] is True
    assert g["crypto_min_usd"] == float(DEFAULT_CRYPTO_ENTRY_MIN_USD)
    assert "stables" in g["line"]
    assert "leveraged" in g["line"]
    assert "noise" in g["line"]
    assert f"${DEFAULT_CRYPTO_ENTRY_MIN_USD:g}" in g["line"]


def test_junk_filter_glance_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["junk_filter_glance"]
    assert g["ready"] is True
    assert "stables" in g["line"]
    assert g["crypto_min_usd"] == float(DEFAULT_CRYPTO_ENTRY_MIN_USD)


def test_junk_filter_glance_in_chart_payload(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    g = load_chart_payload(tmp_path)["junk_filter_glance"]
    assert g["ready"] is True
    assert "stables" in g["line"]
    assert g["crypto_min_usd"] == float(DEFAULT_CRYPTO_ENTRY_MIN_USD)
