"""Holding price-coverage honesty (display only; not a gate)."""

from __future__ import annotations

from openbb_backend.desk import build_mark_coverage


def test_mark_coverage_empty() -> None:
    g = build_mark_coverage(None)
    assert g["ready"] is False
    assert g["bit"] == ""
    assert build_mark_coverage([])["ready"] is False


def test_mark_coverage_ok() -> None:
    g = build_mark_coverage([{"marked": True}, {"marked": True}])
    assert g["severity"] == "ok"
    assert g["tone"] == "ok"
    assert g["pct"] == 100.0
    assert g["bit"] == "price coverage ok · 2/2"


def test_mark_coverage_thin() -> None:
    g = build_mark_coverage(
        [{"marked": True}, {"marked": False}, {"marked": False}]
    )
    assert g["severity"] == "thin"
    assert g["tone"] == "warn"
    assert g["marked"] == 1
    assert g["open"] == 3
    assert g["bit"] == "price coverage thin · 1/3"


def test_mark_coverage_none() -> None:
    g = build_mark_coverage([{"marked": False}, {"symbol": "X"}])
    assert g["severity"] == "none"
    assert g["tone"] == "warn"
    assert g["pct"] == 0.0
    assert g["bit"] == "price coverage none · 0/2"
