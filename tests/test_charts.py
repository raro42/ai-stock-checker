#!/usr/bin/env python3
"""Offline tests for desk chart series."""

import json
from pathlib import Path

from openbb_backend.charts import build_equity_curve, load_chart_payload


def _seed(data: Path) -> None:
    (data / "portfolio.json").write_text(
        json.dumps(
            {
                "initial_cash": 100000,
                "cash": 80000,
                "holdings": {"AAPL": 10},
                "avg_buy_price": {"AAPL": 100},
                "total_fees_paid": 1,
            }
        )
    )
    (data / "trades.jsonl").write_text(
        json.dumps(
            {
                "timestamp": "2026-07-20 10:00:00",
                "type": "BUY",
                "symbol": "AAPL",
                "quantity": 10,
                "price": 100,
                "commission": 1,
                "cash_remaining": 89999,
            }
        )
        + "\n"
    )
    (data / "archive").mkdir(parents=True, exist_ok=True)
    (data / "archive" / "opportunities_latest.json").write_text("{}")


def test_equity_curve_from_fills(tmp_path: Path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    pts = build_equity_curve(tmp_path)
    assert len(pts) >= 2
    assert pts[0]["equity"] == 100000
    assert pts[1]["label"].startswith("BUY")


def test_chart_payload_offline(tmp_path: Path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    payload = load_chart_payload(tmp_path)
    assert "equity" in payload and "allocation" in payload
    assert "from_buy" in payload
    assert any(a["symbol"] == "CASH" for a in payload["allocation"])
    assert any(a["symbol"] == "AAPL" for a in payload["allocation"])


def test_price_history_skips_nan(tmp_path: Path, monkeypatch):
    from openbb_backend.charts import fetch_price_history

    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    cache = tmp_path / "chart_bars"
    cache.mkdir()
    (cache / "AAPL.json").write_text(
        json.dumps(
            {
                "symbol": "AAPL",
                "fetched_at": 9e12,
                "points": [
                    {"t": "2026-07-01T00:00:00Z", "close": 100},
                    {"t": "2026-07-02T00:00:00Z", "close": float("nan")},
                    {"t": "2026-07-03T00:00:00Z", "close": 110},
                ],
            }
        )
    )
    pts = fetch_price_history("AAPL", tmp_path, live=False)
    assert len(pts) == 2
    assert all(p["close"] == p["close"] for p in pts)  # no NaN


def test_unrealized_curve_offline(tmp_path: Path, monkeypatch):
    from openbb_backend.charts import build_unrealized_curve

    _seed(tmp_path)
    (tmp_path / "entry_times.json").write_text(
        json.dumps({"AAPL": 1721476800})  # 2024-07-20
    )
    cache = tmp_path / "chart_bars"
    cache.mkdir()
    (cache / "AAPL.json").write_text(
        json.dumps(
            {
                "symbol": "AAPL",
                "fetched_at": 9e12,
                "points": [
                    {"t": "2024-07-20T00:00:00Z", "close": 100},
                    {"t": "2024-07-21T00:00:00Z", "close": 105},
                    {"t": "2024-07-22T00:00:00Z", "close": 110},
                ],
            }
        )
    )
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    pts = build_unrealized_curve(tmp_path, live=False)
    assert len(pts) >= 2
    assert pts[-1]["unrealized"] == 100.0  # 10 * (110-100)
    assert abs(pts[-1]["unrealized_pct"] - 10.0) < 1e-6
    payload = load_chart_payload(tmp_path)
    assert "unrealized" in payload


def test_from_buy_panel_offline(tmp_path: Path, monkeypatch):
    from openbb_backend.charts import build_from_buy_panels

    _seed(tmp_path)
    (tmp_path / "entry_times.json").write_text(
        json.dumps({"AAPL": 1721476800})
    )
    cache = tmp_path / "chart_bars"
    cache.mkdir()
    (cache / "AAPL.json").write_text(
        json.dumps(
            {
                "symbol": "AAPL",
                "fetched_at": 9e12,
                "points": [
                    {"t": "2024-07-19T00:00:00Z", "close": 90},
                    {"t": "2024-07-21T00:00:00Z", "close": 100},
                    {"t": "2024-07-22T00:00:00Z", "close": 110},
                ],
            }
        )
    )
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    panels = build_from_buy_panels(tmp_path, live=False)
    assert panels
    aapl = next(p for p in panels if p["symbol"] == "AAPL")
    assert aapl["buy_price"] == 100
    assert aapl["points"][0]["rebased"] == 100
    assert aapl["change_pct"] == 10.0
    assert aapl["first_t"]
    assert aapl["last_t"]
    assert "span_hours" in aapl
    assert aapl["span_hours"] >= 0
