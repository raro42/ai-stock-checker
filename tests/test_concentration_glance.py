"""Largest-name vs entry concentration cap glance (display only)."""

from __future__ import annotations

from openbb_backend.desk import build_concentration_glance, load_desk_snapshot


def test_concentration_glance_empty_input() -> None:
    assert build_concentration_glance(None)["ready"] is False
    assert build_concentration_glance("x")["ready"] is False  # type: ignore[arg-type]


def test_concentration_glance_cap_off() -> None:
    g = build_concentration_glance(
        {"largest_symbol": "AAPL", "largest_pct": 10.0},
        max_name_pct=0,
    )
    assert g["ready"] is True
    assert g["tone"] == "off"
    assert "off" in g["line"]


def test_concentration_glance_no_names() -> None:
    g = build_concentration_glance(
        {
            "largest_symbol": "",
            "largest_pct": 0.0,
            "concentration_warn": False,
            "posture": "open",
            "slots": "0/5",
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "clear"
    assert g["warn"] is False
    assert "no open names" in g["line"]
    assert "30%" in g["line"]
    assert g["headroom_pp"] == 30.0


def test_concentration_glance_headroom() -> None:
    g = build_concentration_glance(
        {
            "largest_symbol": "aapl",
            "largest_pct": 18.0,
            "concentration_warn": False,
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "clear"
    assert g["symbol"] == "AAPL"
    assert g["warn"] is False
    assert g["headroom_pp"] == 12.0
    assert "AAPL" in g["line"]
    assert "12pp headroom" in g["line"]


def test_concentration_glance_warn() -> None:
    g = build_concentration_glance(
        {
            "largest_symbol": "JPM",
            "largest_pct": 40.0,
            "concentration_warn": True,
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["warn"] is True
    assert "WARN" in g["line"]
    assert "JPM" in g["line"]
    assert "30%" in g["line"]
    assert g["headroom_pp"] == 0.0


def test_concentration_glance_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["concentration_glance"]
    assert g["ready"] is True
    assert "cap" in g["line"].lower() or "30%" in g["line"]


def test_concentration_glance_in_chart_payload(tmp_path) -> None:
    from openbb_backend.charts import load_chart_payload

    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    g = load_chart_payload(tmp_path)["concentration_glance"]
    assert g["ready"] is True
    assert "cap" in g["line"].lower() or "30%" in g["line"]
