import json
from pathlib import Path

from openbb_backend.desk import (
    RECENT_FILLS_LIMIT,
    _coerce_recent_fills_limit,
    _fill_commission,
    _fill_signed,
    _serialize_trade_row,
    load_desk_snapshot,
)


def test_serialize_trade_row_includes_exit_reason() -> None:
    row = _serialize_trade_row(
        {
            "timestamp": "t",
            "type": "SELL",
            "symbol": "CACI",
            "quantity": 1,
            "price": 100,
            "commission": 1,
            "exit_reason": "sl",
            "note": "Stop loss -6.1%",
            "profit_loss": -6.1,
            "profit_loss_pct": -6.1,
        },
        {},
    )
    assert row["exit_reason"] == "sl"
    assert row["note"] == "Stop loss -6.1%"
    assert row["fill_ok"] is True
    assert row["quantity"] == 1.0
    assert row["price"] == 100.0
    assert row["commission"] == 1.0
    assert row["profit_loss"] == -6.1


def test_serialize_trade_row_refuses_invalid_fills() -> None:
    """tradermonty #700/#655 + Charts parity: bool/0 must not invent desk fills."""
    bad_qty = _serialize_trade_row(
        {"timestamp": "t", "type": "BUY", "symbol": "X", "quantity": True, "price": 50},
        {},
    )
    assert bad_qty["fill_ok"] is False
    assert bad_qty["quantity"] is None
    assert bad_qty["price"] == 50.0

    bad_px = _serialize_trade_row(
        {"timestamp": "t", "type": "BUY", "symbol": "X", "quantity": 2, "price": 0},
        {},
    )
    assert bad_px["fill_ok"] is False
    assert bad_px["price"] is None
    assert bad_px["quantity"] == 2.0

    bad_fee = _serialize_trade_row(
        {
            "timestamp": "t",
            "type": "BUY",
            "symbol": "X",
            "quantity": 2,
            "price": 50,
            "commission": True,
        },
        {},
    )
    assert bad_fee["fill_ok"] is False
    assert bad_fee["commission"] is None

    invent_pnl = _serialize_trade_row(
        {
            "timestamp": "t",
            "type": "SELL",
            "symbol": "X",
            "quantity": 1,
            "price": 50,
            "commission": 0,
            "profit_loss": True,
            "profit_loss_pct": True,
        },
        {},
    )
    assert invent_pnl["fill_ok"] is True
    assert invent_pnl["profit_loss"] is None
    assert invent_pnl["profit_loss_pct"] is None


def test_fill_commission_allows_zero_refuses_bool() -> None:
    assert _fill_commission(None) == 0.0
    assert _fill_commission(0) == 0.0
    assert _fill_commission(1.25) == 1.25
    assert _fill_commission(True) is None
    assert _fill_commission(-1) is None


def test_fill_signed_refuses_bool_exit_euro_ratios() -> None:
    """Window A exit-€ desk: isinstance(True, int) must not invent 1.0× ratios."""
    # Python traps: True is an int subclass — bare isinstance accepts it.
    assert isinstance(True, (int, float)) is True
    assert _fill_signed(True) is None
    assert _fill_signed(False) is None
    assert _fill_signed(2.5) == 2.5
    assert _fill_signed(-0.5) == -0.5
    assert _fill_signed(0) == 0.0
    assert _fill_signed(None) is None
    assert _fill_signed(float("nan")) is None


def test_fill_signed_refuses_bool_window_a_edge_and_laya() -> None:
    """Window A edge/LAYA/postmortem: float(True) must not invent 1.0× / +1% / edge."""
    # try/except float(True) succeeds — claim honesty needs _fill_signed.
    assert float(True) == 1.0
    assert _fill_signed(True) is None
    assert _fill_signed(1.75) == 1.75
    assert _fill_signed(-3.2) == -3.2


def test_fill_signed_refuses_bool_window_a_exit_euro_mid_cascade() -> None:
    """Window A exit-€ mid cascade: float(True)/int(True) must not invent ratios·€·n."""
    from stock_checker.technical_indicators import coerce_nonneg_int

    assert float(True) == 1.0
    assert int(True) == 1
    assert _fill_signed(True) is None
    assert _fill_signed(1.25) == 1.25
    assert coerce_nonneg_int(True) is None
    assert coerce_nonneg_int(3) == 3
    assert coerce_nonneg_int(False) is None


def test_recent_fills_limit_is_twenty() -> None:
    assert RECENT_FILLS_LIMIT == 20


def test_recent_fills_refuses_bool_limit(tmp_path: Path, monkeypatch) -> None:
    """True→1 must not invent a one-fill Recent strip via rows[:True]."""
    assert _coerce_recent_fills_limit(True) == RECENT_FILLS_LIMIT
    assert _coerce_recent_fills_limit(False) == RECENT_FILLS_LIMIT
    assert _coerce_recent_fills_limit(0) == RECENT_FILLS_LIMIT
    assert _coerce_recent_fills_limit(None) == RECENT_FILLS_LIMIT
    assert _coerce_recent_fills_limit(5) == 5

    (tmp_path / "portfolio.json").write_text(
        json.dumps(
            {
                "initial_cash": 100000,
                "cash": 90000,
                "holdings": {"AAPL": 10},
                "avg_buy_price": {"AAPL": 100},
                "total_fees_paid": 0,
            }
        )
    )
    lines = []
    for i in range(5):
        lines.append(
            json.dumps(
                {
                    "timestamp": f"2026-11-2{i} 10:00:00",
                    "type": "BUY",
                    "symbol": "AAPL",
                    "quantity": 1,
                    "price": 100 + i,
                    "commission": 1,
                    "cash_remaining": 90000,
                }
            )
        )
    (tmp_path / "trades.jsonl").write_text("\n".join(lines) + "\n")
    (tmp_path / "archive").mkdir(parents=True, exist_ok=True)
    (tmp_path / "archive" / "opportunities_latest.json").write_text("{}")
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")

    # Bool ceilings must keep the full default strip (5 fills << 20).
    snap_true = load_desk_snapshot(tmp_path, live_marks=False, fills_n=True)
    assert snap_true["recent_fills_limit"] == RECENT_FILLS_LIMIT
    assert len(snap_true["recent_trades"]) == 5
    assert snap_true["older_trades"] == []
    assert snap_true["trade_count"] == 5

    snap_false = load_desk_snapshot(tmp_path, live_marks=False, fills_n=False)
    assert snap_false["recent_fills_limit"] == RECENT_FILLS_LIMIT
    assert len(snap_false["recent_trades"]) == 5

    snap_two = load_desk_snapshot(tmp_path, live_marks=False, fills_n=2)
    assert snap_two["recent_fills_limit"] == 2
    assert len(snap_two["recent_trades"]) == 2
    assert len(snap_two["older_trades"]) == 3
    assert snap_two["trade_count"] == 5
