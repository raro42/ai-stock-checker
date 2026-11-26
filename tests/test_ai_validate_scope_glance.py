"""FinRobot AI validate top-N scope glance (display only)."""

from __future__ import annotations

from pathlib import Path

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import (
    AI_VALIDATE_SCOPE_LINE_CHARS,
    _clip_ai_validate_scope_line,
    _coerce_ai_validate_scope_line_chars,
    build_ai_validate_scope_glance,
    load_desk_snapshot,
)
from stock_checker.intelligent_trader import (
    AI_FULL_TOP_N,
    AI_VALIDATE_TOP_N,
    _coerce_ai_validate_top_n,
)


def test_coerce_ai_validate_top_n_refuses_bool() -> None:
    """FinRobot strip: True→1 must not invent a one-name LLM check."""
    assert _coerce_ai_validate_top_n(True) == AI_VALIDATE_TOP_N
    assert _coerce_ai_validate_top_n(False) == AI_VALIDATE_TOP_N
    assert _coerce_ai_validate_top_n(0) == AI_VALIDATE_TOP_N
    assert _coerce_ai_validate_top_n(None) == AI_VALIDATE_TOP_N
    assert _coerce_ai_validate_top_n(3) == 3
    assert (
        _coerce_ai_validate_top_n(True, default=AI_FULL_TOP_N) == AI_FULL_TOP_N
    )


def test_ai_validate_scope_glance_empty() -> None:
    g = build_ai_validate_scope_glance(None)
    assert g["ready"] is False
    assert g["line"] == ""


def test_ai_validate_scope_glance_off() -> None:
    g = build_ai_validate_scope_glance({"ai_mode": "off"})
    assert g["ready"] is True
    assert g["tone"] == "off"
    assert g["top_n"] == 0
    assert "scanner score only" in g["line"]
    assert "no LLM" in g["line"]


def test_ai_validate_scope_glance_validate() -> None:
    g = build_ai_validate_scope_glance({"ai_mode": "validate"})
    assert g["ready"] is True
    assert g["tone"] == "validate"
    assert g["top_n"] == AI_VALIDATE_TOP_N
    assert f"top {AI_VALIDATE_TOP_N}" in g["line"]
    assert "SELL/LOW-HOLD drop" in g["line"]
    assert "rest pass" in g["line"]


def test_ai_validate_scope_glance_full() -> None:
    g = build_ai_validate_scope_glance({"ai_mode": "full"})
    assert g["ready"] is True
    assert g["tone"] == "full"
    assert g["top_n"] == AI_FULL_TOP_N
    assert f"top {AI_FULL_TOP_N}" in g["line"]
    assert "score<-20" in g["line"]


def test_clip_ai_validate_scope_line_refuses_bool_ceiling() -> None:
    """True→1 must not invent line[:True]; False must not wipe via [:False]."""
    long = "x" * 120
    assert len(long) > AI_VALIDATE_SCOPE_LINE_CHARS
    default = _clip_ai_validate_scope_line(long)
    assert len(default) == AI_VALIDATE_SCOPE_LINE_CHARS
    assert default.endswith("…")
    assert default == long[: AI_VALIDATE_SCOPE_LINE_CHARS - 1] + "…"
    assert _clip_ai_validate_scope_line(long, True) == default
    assert _clip_ai_validate_scope_line(long, False) == default
    assert _clip_ai_validate_scope_line(long, 0) == default
    assert _coerce_ai_validate_scope_line_chars(True) == AI_VALIDATE_SCOPE_LINE_CHARS
    assert _coerce_ai_validate_scope_line_chars(False) == AI_VALIDATE_SCOPE_LINE_CHARS
    thin = _clip_ai_validate_scope_line(long, 12)
    assert thin == long[:11] + "…"
    assert len(thin) == 12


def test_ai_validate_scope_glance_refuses_bool_line_ceiling() -> None:
    """line_n=True must not invent a one-char strip; False must not wipe."""
    g = build_ai_validate_scope_glance({"ai_mode": "validate"})
    g_bool = build_ai_validate_scope_glance({"ai_mode": "validate"}, line_n=True)
    g_false = build_ai_validate_scope_glance(
        {"ai_mode": "validate"}, line_n=False
    )
    assert g_bool["line"] == g["line"]
    assert g_false["line"] == g["line"]
    assert len(g["line"]) <= AI_VALIDATE_SCOPE_LINE_CHARS
    g_short = build_ai_validate_scope_glance(
        {"ai_mode": "validate"}, line_n=12
    )
    assert len(g_short["line"]) == 12
    assert g_short["line"].endswith("…")


def test_ai_validate_scope_glance_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["ai_validate_scope_glance"]
    assert g["ready"] is True
    assert g["ai_mode"] in {"off", "validate", "full"}
    assert g["rest_unscored"] is True
    assert g["line"]


def test_ai_validate_scope_glance_in_chart_payload(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "trader_config.json").write_text(
        '{"ai_mode": "full"}',
        encoding="utf-8",
    )
    g = load_chart_payload(tmp_path)["ai_validate_scope_glance"]
    assert g["ready"] is True
    assert g["tone"] == "full"
    assert f"top {AI_FULL_TOP_N}" in g["line"]


def test_ai_validate_scope_parity_templates() -> None:
    """Screener / Ideas / Book / Breadth / scan-log must show the glance."""
    root = Path(__file__).resolve().parents[1] / "openbb_backend" / "templates"
    for name in (
        "desk_screener.html",
        "desk_ideas.html",
        "desk_book.html",
        "desk_breadth.html",
        "desk_scan_log.html",
    ):
        text = (root / name).read_text(encoding="utf-8")
        assert "ai_validate_scope_glance" in text, name
    charts_js = (
        Path(__file__).resolve().parents[1]
        / "openbb_backend"
        / "static"
        / "charts.js"
    ).read_text(encoding="utf-8")
    assert "renderAiValidateScopeGlance" in charts_js
    assert "ai_validate_scope_glance" in charts_js
