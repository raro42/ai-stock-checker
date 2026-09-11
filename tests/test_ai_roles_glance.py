"""FinRobot multi-role research contract glance (display only)."""

from __future__ import annotations

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import build_ai_roles_glance, load_desk_snapshot


def test_ai_roles_glance_line() -> None:
    g = build_ai_roles_glance()
    assert g["ready"] is True
    assert g["tone"] == "roles"
    assert g["roles"] == ("bull", "bear", "risk")
    assert g["disagree_forces_hold"] is True
    assert g["risk_veto_forces_hold"] is True
    assert "bull" in g["line"]
    assert "bear" in g["line"]
    assert "risk" in g["line"]
    assert "disagree→HOLD" in g["line"]
    assert "risk.ok=false→HOLD" in g["line"]


def test_ai_roles_glance_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["ai_roles_glance"]
    assert g["ready"] is True
    assert g["tone"] == "roles"
    assert "bull" in g["line"]
    assert "HOLD" in g["line"]


def test_ai_roles_glance_in_chart_payload(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    g = load_chart_payload(tmp_path)["ai_roles_glance"]
    assert g["ready"] is True
    assert g["tone"] == "roles"
    assert "disagree→HOLD" in g["line"]
    assert "risk.ok=false→HOLD" in g["line"]
