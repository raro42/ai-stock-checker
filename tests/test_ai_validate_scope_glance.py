"""FinRobot AI validate top-N scope glance (display only)."""

from __future__ import annotations

from pathlib import Path

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import build_ai_validate_scope_glance, load_desk_snapshot
from stock_checker.intelligent_trader import AI_FULL_TOP_N, AI_VALIDATE_TOP_N


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
