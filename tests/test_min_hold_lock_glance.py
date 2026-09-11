"""Min-hold lock glance + holding annotation (display only)."""

from __future__ import annotations

from openbb_backend.desk import (
    apply_min_hold_lock_fields,
    build_min_hold_lock_glance,
)


def test_min_hold_lock_glance_empty() -> None:
    assert build_min_hold_lock_glance(None)["ready"] is False
    assert build_min_hold_lock_glance([])["ready"] is False
    assert build_min_hold_lock_glance([{"symbol": "AAPL"}])["ready"] is False


def test_min_hold_lock_glance_all_unlocked() -> None:
    g = build_min_hold_lock_glance(
        [
            {"symbol": "AAPL", "held_seconds": 90_000},
            {"symbol": "MSFT", "held_seconds": 100_000},
        ],
        min_hold_hours=24,
    )
    assert g["ready"] is True
    assert g["tone"] == "quiet"
    assert g["locked"] == 0
    assert g["timed"] == 2
    assert "all 2 past min-hold" in g["line"]
    assert "rotate/trim OK" in g["line"]


def test_min_hold_lock_glance_partial_lock() -> None:
    g = build_min_hold_lock_glance(
        [
            {"symbol": "AAPL", "held_seconds": 3_600},
            {"symbol": "MSFT", "held_seconds": 100_000},
            {"symbol": "BTC-USD", "held_seconds": 7_200},
        ],
        min_hold_hours=24,
    )
    assert g["ready"] is True
    assert g["tone"] == "flat"
    assert g["locked"] == 2
    assert g["timed"] == 3
    assert g["earliest_symbol"] == "BTC-USD"
    assert "2/3 in min-hold lock" in g["line"]
    assert "BTC-USD" in g["line"]


def test_min_hold_lock_glance_all_locked() -> None:
    g = build_min_hold_lock_glance(
        [{"symbol": "AAPL", "held_seconds": 600}],
        min_hold_hours=24,
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["locked"] == 1
    assert g["earliest_symbol"] == "AAPL"


def test_apply_min_hold_lock_fields_locked() -> None:
    row = {"symbol": "AAPL", "held_seconds": 3600.0}
    out = apply_min_hold_lock_fields(row, 24 * 3600)
    assert out["past_min_hold"] is False
    assert out["min_hold_left_seconds"] == 23 * 3600
    assert out["min_hold_note"].startswith("unlock")


def test_apply_min_hold_lock_fields_past() -> None:
    row = {"symbol": "AAPL", "held_seconds": 100_000.0}
    out = apply_min_hold_lock_fields(row, 24 * 3600)
    assert out["past_min_hold"] is True
    assert out["min_hold_left_seconds"] == 0.0
    assert out["min_hold_note"] == "past min-hold"
    assert out["min_hold_left"] == ""


def test_apply_min_hold_lock_fields_missing_entry() -> None:
    row = {"symbol": "AAPL", "held_seconds": None}
    out = apply_min_hold_lock_fields(row, 24 * 3600)
    assert out["past_min_hold"] is False
    assert out["min_hold_note"] == ""
