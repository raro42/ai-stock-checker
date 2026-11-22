from openbb_backend.desk import (
    RECENT_FILLS_LIMIT,
    _fill_commission,
    _fill_signed,
    _serialize_trade_row,
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


def test_recent_fills_limit_is_twenty() -> None:
    assert RECENT_FILLS_LIMIT == 20
