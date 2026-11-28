"""Overview ret_pct must not invent calm +0.00% when start capital is missing."""

from __future__ import annotations

import json
from pathlib import Path

from openbb_backend.desk import load_desk_snapshot


def _write_book(tmp: Path, portfolio: dict) -> None:
    (tmp / "portfolio.json").write_text(json.dumps(portfolio))
    (tmp / "trades.jsonl").write_text("")


def test_ret_pct_none_when_initial_missing(tmp_path: Path) -> None:
    _write_book(
        tmp_path,
        {"cash": 100_000, "holdings": {}, "avg_buy_price": {}, "total_fees_paid": 0},
    )
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    assert snap["initial"] is None
    assert snap["ret_pct"] is None
    assert snap["equity"] == 100_000.0


def test_ret_pct_none_when_initial_bool(tmp_path: Path) -> None:
    _write_book(
        tmp_path,
        {
            "cash": 50_000,
            "initial_cash": True,
            "holdings": {},
            "avg_buy_price": {},
            "total_fees_paid": 0,
        },
    )
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    assert snap["initial"] is None
    assert snap["ret_pct"] is None


def test_ret_pct_computes_when_initial_ok(tmp_path: Path) -> None:
    _write_book(
        tmp_path,
        {
            "cash": 110_000,
            "initial_cash": 100_000,
            "holdings": {},
            "avg_buy_price": {},
            "total_fees_paid": 0,
        },
    )
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    assert snap["initial"] == 100_000.0
    assert snap["ret_pct"] is not None
    assert abs(float(snap["ret_pct"]) - 10.0) < 1e-9
