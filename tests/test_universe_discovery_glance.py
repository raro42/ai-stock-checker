"""Universe / Yahoo movers discovery glance (display only)."""

from __future__ import annotations

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import build_universe_discovery_glance, load_desk_snapshot
from stock_checker.yahoo_universe_discovery import DEFAULT_MOVER_COUNT


def test_universe_discovery_glance_ready() -> None:
    g = build_universe_discovery_glance()
    assert g["ready"] is True
    assert g["tone"] == "discover"
    assert g["discovery_only"] is True
    assert g["auto_buy"] is False
    assert g["mover_count"] == int(DEFAULT_MOVER_COUNT)
    assert "US+DE" in g["line"]
    assert "discovery-only" in g["line"]
    assert "not auto-buy" in g["line"]
    assert f"≤{DEFAULT_MOVER_COUNT}/screen" in g["line"]


def test_universe_discovery_glance_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["universe_discovery_glance"]
    assert g["ready"] is True
    assert "discovery-only" in g["line"]
    assert g["auto_buy"] is False


def test_universe_discovery_glance_in_chart_payload(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    g = load_chart_payload(tmp_path)["universe_discovery_glance"]
    assert g["ready"] is True
    assert "discovery-only" in g["line"]
    assert g["auto_buy"] is False
