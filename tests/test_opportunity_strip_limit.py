"""Opportunities scan-list strip ceilings refuse bool invent."""

from __future__ import annotations

import json
from pathlib import Path

from openbb_backend.desk import (
    OPPORTUNITY_CRYPTO_STRIP,
    OPPORTUNITY_RECS_STRIP,
    OPPORTUNITY_STOCK_STRIP,
    _coerce_opportunity_strip_limit,
    load_desk_snapshot,
)


def test_opportunity_strip_defaults() -> None:
    assert OPPORTUNITY_RECS_STRIP == 8
    assert OPPORTUNITY_CRYPTO_STRIP == 6
    assert OPPORTUNITY_STOCK_STRIP == 6


def test_opportunity_strip_refuses_bool() -> None:
    assert _coerce_opportunity_strip_limit(True) == OPPORTUNITY_CRYPTO_STRIP
    assert _coerce_opportunity_strip_limit(False) == OPPORTUNITY_CRYPTO_STRIP
    assert _coerce_opportunity_strip_limit(0) == OPPORTUNITY_CRYPTO_STRIP
    assert _coerce_opportunity_strip_limit(None) == OPPORTUNITY_CRYPTO_STRIP
    assert _coerce_opportunity_strip_limit(3) == 3
    assert (
        _coerce_opportunity_strip_limit(True, default=OPPORTUNITY_RECS_STRIP)
        == OPPORTUNITY_RECS_STRIP
    )


def test_load_desk_snapshot_refuses_bool_opportunity_strips(
    tmp_path: Path, monkeypatch
) -> None:
    """True→1 must not invent a one-name Opportunities strip via rows[:True]."""
    (tmp_path / "portfolio.json").write_text(
        json.dumps(
            {
                "initial_cash": 100000,
                "cash": 100000,
                "holdings": {},
                "avg_buy_price": {},
                "total_fees_paid": 0,
            }
        )
    )
    (tmp_path / "trades.jsonl").write_text("")
    archive = tmp_path / "archive"
    archive.mkdir(parents=True, exist_ok=True)
    archive.joinpath("opportunities_latest.json").write_text(
        json.dumps(
            {
                "recommendations": [
                    {"symbol": f"R{i}", "score": 50 + i} for i in range(10)
                ],
                "crypto_leaders": [
                    {
                        "symbol": f"C{i}-USD",
                        "price": 100 + i,
                        "change_24h": 1.0,
                        "score": 40 + i,
                    }
                    for i in range(8)
                ],
                "stock_breakouts": [
                    {
                        "symbol": f"S{i}",
                        "price": 50 + i,
                        "pct_from_high": -1.0,
                    }
                    for i in range(8)
                ],
            }
        )
    )
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")

    # Bool ceilings keep the full default strips (10/8/8 > 8/6/6 → capped).
    snap_true = load_desk_snapshot(
        tmp_path,
        live_marks=False,
        recs_n=True,
        crypto_n=True,
        stock_n=True,
    )
    assert snap_true["opportunity_recs_limit"] == OPPORTUNITY_RECS_STRIP
    assert snap_true["opportunity_crypto_limit"] == OPPORTUNITY_CRYPTO_STRIP
    assert snap_true["opportunity_stock_limit"] == OPPORTUNITY_STOCK_STRIP
    assert len(snap_true["recommendations"]) == OPPORTUNITY_RECS_STRIP
    assert len(snap_true["crypto_leaders"]) == OPPORTUNITY_CRYPTO_STRIP
    assert len(snap_true["stock_breakouts"]) == OPPORTUNITY_STOCK_STRIP
    # Pulse still sees full scan lists.
    assert snap_true["scan_breadth"]["crypto_n"] == 8
    assert snap_true["scan_breadth"]["stock_breakouts_n"] == 8

    snap_false = load_desk_snapshot(
        tmp_path,
        live_marks=False,
        recs_n=False,
        crypto_n=False,
        stock_n=False,
    )
    assert snap_false["opportunity_recs_limit"] == OPPORTUNITY_RECS_STRIP
    assert len(snap_false["recommendations"]) == OPPORTUNITY_RECS_STRIP
    assert len(snap_false["crypto_leaders"]) == OPPORTUNITY_CRYPTO_STRIP
    assert len(snap_false["stock_breakouts"]) == OPPORTUNITY_STOCK_STRIP

    snap_two = load_desk_snapshot(
        tmp_path,
        live_marks=False,
        recs_n=2,
        crypto_n=2,
        stock_n=2,
    )
    assert snap_two["opportunity_recs_limit"] == 2
    assert snap_two["opportunity_crypto_limit"] == 2
    assert snap_two["opportunity_stock_limit"] == 2
    assert len(snap_two["recommendations"]) == 2
    assert len(snap_two["crypto_leaders"]) == 2
    assert len(snap_two["stock_breakouts"]) == 2
    # Absolute pulse counts stay full even when UI strip is thin.
    assert snap_two["scan_breadth"]["crypto_n"] == 8
    assert snap_two["scan_breadth"]["stock_breakouts_n"] == 8
