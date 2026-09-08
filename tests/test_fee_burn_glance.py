"""Fee-burn glance (display only)."""

from __future__ import annotations

from openbb_backend.desk import build_fee_burn_glance


def test_fee_burn_glance_empty() -> None:
    assert build_fee_burn_glance(None, None)["ready"] is False
    assert build_fee_burn_glance(0, 10_000)["ready"] is False
    assert build_fee_burn_glance(50, 0)["ready"] is False
    assert build_fee_burn_glance(-1, 10_000)["ready"] is False


def test_fee_burn_glance_quiet() -> None:
    g = build_fee_burn_glance(50.0, 10_000.0)
    assert g["ready"] is True
    assert g["tone"] == "quiet"
    assert g["high"] is False
    assert "€50.00" in g["line"]
    assert "0.5%" in g["line"]
    assert "quiet" in g["line"]


def test_fee_burn_glance_warn() -> None:
    g = build_fee_burn_glance(250.0, 10_000.0)
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["high"] is True
    assert "2.5%" in g["line"]
    assert "high" in g["line"]


def test_fee_burn_glance_threshold_edge() -> None:
    g = build_fee_burn_glance(200.0, 10_000.0, threshold=0.02)
    assert g["ready"] is True
    assert g["high"] is True
    assert g["tone"] == "warn"
