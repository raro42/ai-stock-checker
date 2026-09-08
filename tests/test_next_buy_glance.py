"""Next-buy sizer glance (tradermonty / portfolio AI; display only)."""

from __future__ import annotations

from openbb_backend.desk import build_next_buy_glance


def test_next_buy_glance_empty() -> None:
    assert build_next_buy_glance(None)["ready"] is False
    assert build_next_buy_glance({})["ready"] is False
    assert build_next_buy_glance({"eur": 100})["ready"] is False


def test_next_buy_glance_open() -> None:
    g = build_next_buy_glance(
        {
            "eur": 7610.0,
            "cash_frac": 0.1,
            "slots_open": 2,
            "capped_by": "cash_frac",
            "note": "~10% of cash (2 slots open)",
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "open"
    assert g["eur"] == 7610.0
    assert g["slots_open"] == 2
    assert "Next buy ~€7,610" in g["line"]
    assert "2 slots open" in g["line"]


def test_next_buy_glance_concentration_warn() -> None:
    g = build_next_buy_glance(
        {
            "eur": 500.0,
            "slots_open": 1,
            "capped_by": "concentration",
            "note": "~10% cash · capped at 30% equity",
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert "Next buy ~€500" in g["line"]


def test_next_buy_glance_book_full() -> None:
    g = build_next_buy_glance(
        {
            "eur": 0.0,
            "slots_open": 0,
            "capped_by": "book_full",
            "note": "book full (5/5)",
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["line"].startswith("No new buy")
    assert "book full" in g["line"]


def test_next_buy_glance_line_cap() -> None:
    g = build_next_buy_glance(
        {
            "eur": 1.0,
            "slots_open": 1,
            "capped_by": "cash_frac",
            "note": "x" * 120,
        }
    )
    assert g["ready"] is True
    assert len(g["line"]) <= 96
    assert g["line"].endswith("…")
