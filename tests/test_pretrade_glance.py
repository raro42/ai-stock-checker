"""Pre-trade PASS/WARN/FAIL glance (display only)."""

from __future__ import annotations

from openbb_backend.desk import build_pretrade_glance


def test_pretrade_glance_empty() -> None:
    assert build_pretrade_glance(None, None)["ready"] is False
    assert build_pretrade_glance("", [])["ready"] is False
    assert build_pretrade_glance("maybe", ["ok"])["ready"] is False


def test_pretrade_glance_pass() -> None:
    g = build_pretrade_glance("pass", ["ok"])
    assert g["ready"] is True
    assert g["level"] == "PASS"
    assert g["tone"] == "pass"
    assert g["line"] == "PASS · ok"
    assert g["notes"] == ["ok"]


def test_pretrade_glance_warn_joins_notes() -> None:
    g = build_pretrade_glance(
        "WARN",
        ["UTC day realized €-12.00", "fee burn high vs PnL"],
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert "WARN ·" in g["line"]
    assert "fee burn" in g["line"]


def test_pretrade_glance_fail_truncates() -> None:
    long = "x" * 120
    g = build_pretrade_glance("FAIL", [long])
    assert g["ready"] is True
    assert g["tone"] == "fail"
    assert g["line"].endswith("…")
    assert len(g["line"]) <= 110
