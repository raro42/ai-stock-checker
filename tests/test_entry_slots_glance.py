"""Entry score band + interleave honesty glance (A11; display only)."""

from __future__ import annotations

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import build_entry_slots_glance, load_desk_snapshot
from stock_checker.entry_slots import (
    DEFAULT_MAX_CRYPTO_SLOTS,
    DEFAULT_MAX_STOCK_SLOTS,
    STOCK_BREAKOUT_SCORE_BASE,
)


def test_entry_slots_glance_ready() -> None:
    g = build_entry_slots_glance()
    assert g["ready"] is True
    assert g["tone"] == "slots"
    assert g["pure_global_sort"] is False
    assert g["score_base"] == float(STOCK_BREAKOUT_SCORE_BASE)
    assert g["max_crypto_slots"] == int(DEFAULT_MAX_CRYPTO_SLOTS)
    assert g["max_stock_slots"] == int(DEFAULT_MAX_STOCK_SLOTS)
    assert "pct_from_high" in g["line"]
    assert "interleave" in g["line"]
    assert "not pure sort" in g["line"]
    assert f"{STOCK_BREAKOUT_SCORE_BASE:g}+" in g["line"]


def test_entry_slots_glance_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["entry_slots_glance"]
    assert g["ready"] is True
    assert g["pure_global_sort"] is False
    assert "interleave" in g["line"]


def test_entry_slots_glance_in_chart_payload(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    g = load_chart_payload(tmp_path)["entry_slots_glance"]
    assert g["ready"] is True
    assert g["pure_global_sort"] is False
    assert "pct_from_high" in g["line"]
