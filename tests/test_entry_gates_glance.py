"""Entry-gates glance (display only)."""

from __future__ import annotations

from openbb_backend.desk import build_entry_gates_glance


def test_entry_gates_glance_empty() -> None:
    assert build_entry_gates_glance(None)["ready"] is False
    assert build_entry_gates_glance({})["ready"] is False


def test_entry_gates_glance_strict() -> None:
    g = build_entry_gates_glance(
        {
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "promote_experiment_strategy": False,
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "strict"
    assert g["soft_on"] == 3
    assert g["regime"] is True
    assert g["promote"] is False
    assert "regime on" in g["line"]
    assert "promote off" in g["line"]


def test_entry_gates_glance_mixed() -> None:
    g = build_entry_gates_glance(
        {
            "regime_gate": True,
            "rs_gate": False,
            "breadth_gate": True,
            "promote_experiment_strategy": True,
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "mixed"
    assert g["soft_on"] == 2
    assert g["rs"] is False
    assert g["promote"] is True
    assert "RS off" in g["line"]
    assert "promote on" in g["line"]


def test_entry_gates_glance_loose() -> None:
    g = build_entry_gates_glance(
        {
            "regime_gate": False,
            "rs_gate": False,
            "breadth_gate": False,
            "promote_experiment_strategy": False,
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "loose"
    assert g["soft_on"] == 0
    assert "regime off" in g["line"]
    assert "breadth off" in g["line"]
