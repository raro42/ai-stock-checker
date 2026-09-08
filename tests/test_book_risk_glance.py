"""Book risk glance (display only)."""

from __future__ import annotations

from openbb_backend.desk import build_book_risk_glance


def test_book_risk_glance_empty() -> None:
    assert build_book_risk_glance(None)["ready"] is False
    assert build_book_risk_glance({})["ready"] is False
    assert build_book_risk_glance({"posture": "open"})["ready"] is False


def test_book_risk_glance_open() -> None:
    g = build_book_risk_glance(
        {
            "slots": "2/5",
            "posture": "open",
            "note": "2/5 slots · open · cash 40%",
            "concentration_warn": False,
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "open"
    assert g["posture"] == "open"
    assert g["slots"] == "2/5"
    assert "2/5 slots" in g["line"]
    assert g["concentration_warn"] is False


def test_book_risk_glance_overweight() -> None:
    g = build_book_risk_glance(
        {
            "slots": "6/5",
            "posture": "overweight",
            "note": "6/5 slots · overweight · largest AAPL 35%",
            "concentration_warn": True,
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "overweight"
    assert g["posture"] == "overweight"
    assert g["concentration_warn"] is True


def test_book_risk_glance_truncates_note() -> None:
    long = "x" * 120
    g = build_book_risk_glance(
        {"slots": "1/5", "posture": "at_cap", "note": long}
    )
    assert g["ready"] is True
    assert g["tone"] == "at_cap"
    assert g["line"].endswith("…")
    assert len(g["line"]) <= 96
