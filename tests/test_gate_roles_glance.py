"""Gate roles honesty glance (A14; display only)."""

from __future__ import annotations

from openbb_backend.desk import build_gate_roles_glance, load_desk_snapshot


def test_gate_roles_glance_overlap() -> None:
    g = build_gate_roles_glance(
        {"regime_gate": True, "rs_gate": True, "breadth_gate": True}
    )
    assert g["ready"] is True
    assert g["tone"] == "overlap"
    assert g["overlap"] is True
    assert g["prefer_rs_off_if_starved"] is True
    assert "starve→RS off first" in g["line"]
    assert "abs vs rel" in g["line"]
    assert "benchmark trend" in g["regime_role"]
    assert "relative" in g["rs_role"]
    assert "scan-list" in g["breadth_role"]


def test_gate_roles_glance_no_overlap() -> None:
    g = build_gate_roles_glance(
        {"regime_gate": True, "rs_gate": False, "breadth_gate": True}
    )
    assert g["ready"] is True
    assert g["tone"] == "roles"
    assert g["overlap"] is False
    assert g["regime"] is True
    assert g["rs"] is False
    assert "RS off" in g["line"]
    assert "starve→RS off first" in g["line"]


def test_gate_roles_glance_empty_runtime() -> None:
    g = build_gate_roles_glance(None)
    assert g["ready"] is False
    assert g["line"] == ""


def test_gate_roles_glance_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["gate_roles_glance"]
    assert g["ready"] is True
    assert g["prefer_rs_off_if_starved"] is True
    assert "RS off first" in g["line"] or "starve→RS off first" in g["line"]
