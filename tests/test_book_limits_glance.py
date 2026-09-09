"""Book limits + fee schedule glance (display only)."""

from __future__ import annotations

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import build_book_limits_glance


def test_book_limits_glance_empty() -> None:
    assert build_book_limits_glance(None)["ready"] is False
    assert build_book_limits_glance({})["ready"] is False
    assert build_book_limits_glance({"max_positions": 5})["ready"] is False


def test_book_limits_glance_defaults() -> None:
    g = build_book_limits_glance(
        {
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "book"
    assert g["max_positions"] == 5
    assert g["min_hold_hours"] == 24.0
    assert g["fee_preset"] == "revolut_standard"
    assert "5 slots" in g["line"]
    assert "≥24h hold" in g["line"] or ">=24h hold" in g["line"]
    assert "Revolut Std" in g["line"]
    assert "0.25%" in g["line"]


def test_book_limits_glance_warn_short_hold() -> None:
    g = build_book_limits_glance(
        {
            "max_positions": 5,
            "min_hold_hours": 2,
            "fee_preset": "revolut_standard",
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert "≥2h hold" in g["line"] or ">=2h hold" in g["line"]


def test_book_limits_glance_optimistic_spot_fees() -> None:
    g = build_book_limits_glance(
        {
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "binance_like",
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "optimistic"
    assert "Spot-like" in g["line"]


def test_book_limits_glance_in_chart_payload(tmp_path) -> None:
    payload = load_chart_payload(tmp_path)
    g = payload["book_limits_glance"]
    assert g["ready"] is True
    assert g["max_positions"] >= 1
    assert "slots" in g["line"]
