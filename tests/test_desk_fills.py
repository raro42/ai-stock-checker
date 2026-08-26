from openbb_backend.desk import RECENT_FILLS_LIMIT, _serialize_trade_row


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
        },
        {},
    )
    assert row["exit_reason"] == "sl"
    assert row["note"] == "Stop loss -6.1%"


def test_recent_fills_limit_is_twenty() -> None:
    assert RECENT_FILLS_LIMIT == 20
