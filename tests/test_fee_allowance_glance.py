"""Fee allowance honesty glance (portfolio AI / Revolut free legs; display only)."""

from __future__ import annotations

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import build_fee_allowance_glance, load_desk_snapshot


def test_fee_allowance_glance_empty() -> None:
    assert build_fee_allowance_glance(None)["ready"] is False
    g = build_fee_allowance_glance({})
    assert g["ready"] is True
    assert g["tone"] == "none"
    assert g["crypto_modeled"] is False
    assert "crypto fees not modeled" in g["line"]


def test_fee_allowance_glance_open() -> None:
    g = build_fee_allowance_glance(
        {
            "fee_preset": "revolut_standard",
            "free_legs_per_month": 1,
            "fee_allowance_remaining": 1,
            "fee_allowance_used": 0,
            "fee_allowance_month": "2026-09",
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "open"
    assert g["remaining"] == 1
    assert g["free_legs"] == 1
    assert "1/1 free left" in g["line"]
    assert "2026-09" in g["line"]
    assert "Revolut Std" in g["line"]
    assert "crypto not modeled" in g["line"]


def test_fee_allowance_glance_spent() -> None:
    g = build_fee_allowance_glance(
        {
            "fee_preset": "revolut_plus",
            "free_legs_per_month": 3,
            "fee_allowance_remaining": 0,
            "fee_allowance_used": 3,
            "fee_allowance_month": "2026-09",
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "spent"
    assert g["remaining"] == 0
    assert "0/3 free left" in g["line"]
    assert "then paid legs" in g["line"]
    assert "crypto fees not modeled" in g["line"]


def test_fee_allowance_glance_derives_remaining() -> None:
    g = build_fee_allowance_glance(
        {
            "fee_preset": "revolut_ultra",
            "free_legs_per_month": 10,
            "fee_allowance_used": 2,
            "fee_allowance_month": "2026-09",
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "open"
    assert g["remaining"] == 8
    assert "8/10 free left" in g["line"]


def test_fee_allowance_glance_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0, "free_legs_per_month": 1, '
        '"fee_allowance_used": 0, "fee_allowance_month": "2026-09"}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["fee_allowance_glance"]
    assert g["ready"] is True
    assert g["crypto_modeled"] is False
    assert "free" in g["line"].lower() or "no free" in g["line"].lower()


def test_fee_allowance_glance_in_chart_payload(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0, "free_legs_per_month": 1, '
        '"fee_allowance_used": 0, "fee_allowance_month": "2026-09"}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    g = load_chart_payload(tmp_path)["fee_allowance_glance"]
    assert g["ready"] is True
    assert g["crypto_modeled"] is False
    assert "free" in g["line"].lower() or "no free" in g["line"].lower()
