"""RyanJHamby / xang1234 soft-gate params glance (display only)."""

from __future__ import annotations

from pathlib import Path

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import build_gate_params_glance, load_desk_snapshot
from stock_checker.market_regime import (
    CRYPTO_SMA_PERIOD,
    STOCK_BENCHMARK,
    STOCK_SMA_PERIOD,
)
from stock_checker.relative_strength import DEFAULT_RS_LOOKBACK, RS_ANCHOR_MAX_MISS
from stock_checker.scan_breadth_gate import (
    DEFAULT_MIN_ADVANCE_RATIO,
    DEFAULT_MIN_STOCK_LEADERS,
)


def test_gate_params_glance_line() -> None:
    g = build_gate_params_glance()
    assert g["ready"] is True
    assert g["tone"] == "params"
    assert g["fail_open"] is True
    assert g["stock_benchmark"] == STOCK_BENCHMARK
    assert g["stock_sma"] == STOCK_SMA_PERIOD
    assert g["crypto_sma"] == CRYPTO_SMA_PERIOD
    assert g["rs_lookback"] == DEFAULT_RS_LOOKBACK
    assert g["rs_anchor_max_miss"] == RS_ANCHOR_MAX_MISS
    assert g["rs_anchor_max_miss_env"] is False
    assert g["min_advance_ratio"] == DEFAULT_MIN_ADVANCE_RATIO
    assert g["min_stock_leaders"] == DEFAULT_MIN_STOCK_LEADERS
    assert f"SMA{STOCK_SMA_PERIOD}" in g["line"]
    assert f"SMA{CRYPTO_SMA_PERIOD}" in g["line"]
    assert f"{DEFAULT_RS_LOOKBACK}d" in g["line"]
    assert f"gap≤{RS_ANCHOR_MAX_MISS * 100:.0f}%" in g["line"]
    assert "gap≤25% · env" not in g["line"]
    assert "fail-open" in g["line"]


def test_gate_params_glance_gap_env_override(monkeypatch) -> None:
    """Non-default RS_ANCHOR_MAX_MISS speaks gap≤N% · env (xang1234 #539)."""
    monkeypatch.setenv("RS_ANCHOR_MAX_MISS", "0.4")
    g = build_gate_params_glance()
    assert g["rs_anchor_max_miss"] == 0.4
    assert g["rs_anchor_max_miss_env"] is True
    assert "gap≤40% · env" in g["line"]
    monkeypatch.setenv("RS_ANCHOR_MAX_MISS", "50%")  # typo → default
    bad = build_gate_params_glance()
    assert bad["rs_anchor_max_miss"] == RS_ANCHOR_MAX_MISS
    assert bad["rs_anchor_max_miss_env"] is False
    assert "gap≤25% · env" not in bad["line"]


def test_gate_params_glance_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["gate_params_glance"]
    assert g["ready"] is True
    assert g["tone"] == "params"
    assert "SMA200" in g["line"]
    assert "fail-open" in g["line"]


def test_gate_params_glance_in_chart_payload(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    g = load_chart_payload(tmp_path)["gate_params_glance"]
    assert g["ready"] is True
    assert g["rs_lookback"] == DEFAULT_RS_LOOKBACK
    assert "A/D≥" in g["line"]


def test_gate_params_parity_templates() -> None:
    """Overview / Ops / Screener / Ideas / Book / Breadth / scan-log + Charts."""
    root = Path(__file__).resolve().parents[1] / "openbb_backend" / "templates"
    for name in (
        "desk_overview.html",
        "desk_ops.html",
        "desk_screener.html",
        "desk_ideas.html",
        "desk_book.html",
        "desk_breadth.html",
        "desk_scan_log.html",
    ):
        text = (root / name).read_text(encoding="utf-8")
        assert "gate_params_glance" in text, name
    charts_js = (
        Path(__file__).resolve().parents[1]
        / "openbb_backend"
        / "static"
        / "charts.js"
    ).read_text(encoding="utf-8")
    assert "renderGateParamsGlance" in charts_js
    assert "gate_params_glance" in charts_js
