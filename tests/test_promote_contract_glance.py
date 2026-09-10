"""Promote entry-veto contract glance (A18; display only)."""

from __future__ import annotations

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import build_promote_contract_glance, load_desk_snapshot


def test_promote_contract_glance_off() -> None:
    g = build_promote_contract_glance({"promote_experiment_strategy": False})
    assert g["ready"] is True
    assert g["tone"] == "off"
    assert g["promote_on"] is False
    assert g["entry_veto_only"] is True
    assert g["exits_via_champion"] is False
    assert "entry veto only" in g["line"]
    assert "exit_policy" in g["line"]
    assert g["source"] == "experiment_strategy"


def test_promote_contract_glance_on() -> None:
    g = build_promote_contract_glance({"promote_experiment_strategy": True})
    assert g["ready"] is True
    assert g["tone"] == "on"
    assert g["promote_on"] is True
    assert g["entry_veto_only"] is True
    assert g["exits_via_champion"] is False
    assert "SELL ≠ buy" in g["line"]
    assert "exit_policy" in g["line"]


def test_promote_contract_glance_empty_runtime() -> None:
    g = build_promote_contract_glance(None)
    assert g["ready"] is False
    assert g["line"] == ""


def test_promote_contract_glance_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["promote_contract_glance"]
    assert g["ready"] is True
    assert g["entry_veto_only"] is True
    assert "entry veto" in g["line"]


def test_promote_contract_glance_in_chart_payload(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    g = load_chart_payload(tmp_path)["promote_contract_glance"]
    assert g["ready"] is True
    assert g["exits_via_champion"] is False
    assert "exit_policy" in g["line"]
