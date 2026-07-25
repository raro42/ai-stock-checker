#!/usr/bin/env python3
"""Offline tests for OpenBB backend (no httpx required)."""

import json
from pathlib import Path

from openbb_backend import main as backend


def test_portfolio_endpoints_direct(tmp_path: Path, monkeypatch):
    data = tmp_path
    (data / "portfolio.json").write_text(
        json.dumps(
            {
                "initial_cash": 10000,
                "cash": 5000,
                "holdings": {"AAPL": 10},
                "avg_buy_price": {"AAPL": 100},
                "total_fees_paid": 12.5,
                "last_updated": "2026-07-25T00:00:00",
            }
        )
    )
    (data / "trades.jsonl").write_text(
        json.dumps(
            {
                "timestamp": "t",
                "type": "BUY",
                "symbol": "AAPL",
                "quantity": 10,
                "price": 100,
                "commission": 1,
            }
        )
        + "\n"
    )
    monkeypatch.setattr(backend, "DATA_DIR", data)
    monkeypatch.setattr(backend, "API_KEY", "")

    rows = backend.portfolio_table()
    assert rows[0]["symbol"] == "AAPL"
    md = backend.portfolio_markdown().body.decode()
    assert "Paper Portfolio" in md
    trades = backend.trades_table(limit=10)
    assert trades[0]["symbol"] == "AAPL"
    assert backend.health()["ok"] is True
    widgets = json.loads((Path(backend.__file__).parent / "widgets.json").read_text())
    assert "portfolio_markdown" in widgets
