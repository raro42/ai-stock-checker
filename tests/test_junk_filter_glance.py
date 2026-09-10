"""Junk / noise filter policy glance (display only)."""

from __future__ import annotations

from openbb_backend.desk import build_junk_filter_glance, load_desk_snapshot
from stock_checker.exit_policy import DEFAULT_CRYPTO_ENTRY_MIN_USD


def test_junk_filter_glance_ready() -> None:
    g = build_junk_filter_glance()
    assert g["ready"] is True
    assert g["tone"] == "filter"
    assert g["stables_blocked"] is True
    assert g["leveraged_blocked"] is True
    assert g["crypto_min_usd"] == float(DEFAULT_CRYPTO_ENTRY_MIN_USD)
    assert "stables" in g["line"]
    assert "leveraged" in g["line"]
    assert "noise" in g["line"]
    assert f"${DEFAULT_CRYPTO_ENTRY_MIN_USD:g}" in g["line"]


def test_junk_filter_glance_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["junk_filter_glance"]
    assert g["ready"] is True
    assert "stables" in g["line"]
    assert g["crypto_min_usd"] == float(DEFAULT_CRYPTO_ENTRY_MIN_USD)
