"""Cost-shadow marks must not invent calm +0.00% unrealized (xang1234 refuse-shadow)."""

from __future__ import annotations

import json
from pathlib import Path

from openbb_backend.desk import load_desk_snapshot


def _write_book(tmp: Path, portfolio: dict, opportunities: dict | None = None) -> None:
    (tmp / "portfolio.json").write_text(json.dumps(portfolio))
    (tmp / "trades.jsonl").write_text("")
    if opportunities is not None:
        arch = tmp / "archive"
        arch.mkdir(parents=True, exist_ok=True)
        (arch / "opportunities_latest.json").write_text(json.dumps(opportunities))


def test_empty_book_unrealized_pct_zero(tmp_path: Path) -> None:
    _write_book(
        tmp_path,
        {
            "cash": 100_000,
            "initial_cash": 100_000,
            "holdings": {},
            "avg_buy_price": {},
            "total_fees_paid": 0,
        },
    )
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    assert snap["unrealized_pct"] == 0.0
    assert snap["unrealized_total"] == 0.0


def test_cost_shadow_lots_unrealized_pct_none(tmp_path: Path) -> None:
    """Open lots with no scan/live marks → cost fallback → n/a €/%, not +0.00."""
    _write_book(
        tmp_path,
        {
            "cash": 50_000,
            "initial_cash": 100_000,
            "holdings": {"AAPL": 10},
            "avg_buy_price": {"AAPL": 100.0},
            "total_fees_paid": 0,
        },
    )
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    assert snap["holdings"]
    assert snap["unrealized_pct"] is None
    assert snap["holdings"][0]["marked"] is False
    assert snap["holdings"][0]["unrealized_pct"] is None
    assert snap["holdings"][0]["unrealized"] is None
    # Cost fills MV — but last must not invent a live print from avg.
    assert snap["holdings"][0]["last"] is None
    assert abs(float(snap["holdings"][0]["market_value"]) - 1000.0) < 1e-9
    # last=cost by construction — never invent calm +€0.00 on the strip.
    assert snap["unrealized_total"] is None


def test_scan_mark_computes_unrealized_pct(tmp_path: Path) -> None:
    _write_book(
        tmp_path,
        {
            "cash": 50_000,
            "initial_cash": 100_000,
            "holdings": {"AAPL": 10},
            "avg_buy_price": {"AAPL": 100.0},
            "total_fees_paid": 0,
        },
        opportunities={
            "stock_breakouts": [
                {"symbol": "AAPL", "price": 110.0, "score": 50},
            ],
        },
    )
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    assert snap["holdings"][0]["marked"] is True
    assert snap["unrealized_pct"] is not None
    assert abs(float(snap["unrealized_pct"]) - 10.0) < 1e-9
    assert abs(float(snap["holdings"][0]["unrealized_pct"]) - 10.0) < 1e-9


def test_mixed_shadow_unrealized_pct_excludes_unmarked(tmp_path: Path) -> None:
    """Marked + cost-shadow → % over marked cost only (xang1234 #772 gap drop).

    Before: unmarked last=avg invented flat 0% into the book denominator and
    diluted AAPL +10% toward ~+5%. Shadow must drop out, not invent calm.
    """
    _write_book(
        tmp_path,
        {
            "cash": 50_000,
            "initial_cash": 100_000,
            "holdings": {"AAPL": 10, "MSFT": 10},
            "avg_buy_price": {"AAPL": 100.0, "MSFT": 100.0},
            "total_fees_paid": 0,
        },
        opportunities={
            "stock_breakouts": [
                {"symbol": "AAPL", "price": 110.0, "score": 50},
            ],
        },
    )
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    by_sym = {r["symbol"]: r for r in snap["holdings"]}
    assert by_sym["AAPL"]["marked"] is True
    assert by_sym["MSFT"]["marked"] is False
    assert by_sym["MSFT"]["unrealized_pct"] is None
    assert by_sym["MSFT"]["unrealized"] is None
    assert by_sym["MSFT"]["last"] is None
    assert by_sym["AAPL"]["last"] is not None
    assert snap["unrealized_pct"] is not None
    assert abs(float(snap["unrealized_pct"]) - 10.0) < 1e-9
    # € total is marked-only (shadow drops out of both € and %).
    assert abs(float(snap["unrealized_total"]) - 100.0) < 1e-9
