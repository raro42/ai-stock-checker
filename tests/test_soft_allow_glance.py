"""Fail-open soft-allow glance (display only)."""

from __future__ import annotations

from openbb_backend.desk import build_soft_allow_glance


def test_soft_allow_glance_empty() -> None:
    assert build_soft_allow_glance(None)["ready"] is False
    assert build_soft_allow_glance([])["ready"] is False


def test_soft_allow_glance_one() -> None:
    g = build_soft_allow_glance(
        [{"at": "2026-09-08T01:00:00Z", "gate": "regime", "reason": "unknown — no SPY bars"}]
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["count"] == 1
    assert g["last_gate"] == "regime"
    assert "1 recent soft-allow" in g["line"]
    assert "[regime]" in g["line"]
    assert "no SPY bars" in g["line"]


def test_soft_allow_glance_truncates_reason() -> None:
    long = "x" * 100
    g = build_soft_allow_glance(
        [{"at": "t", "gate": "rs", "reason": long}]
    )
    assert g["ready"] is True
    assert g["last_reason"].endswith("…")
    assert len(g["last_reason"]) <= 72
